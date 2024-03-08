import argparse
import csv
import json
import logging
import os
from pathlib import Path

import cv2
import numpy as np
import torch
import torchvision.transforms as transforms
from sort import Sort

from crabs.detection_tracking.detection_utils import draw_bbox


class DetectorInference:
    """
    A class for performing object detection or tracking inference on a video
    using a trained model.

    Parameters:
        args (argparse.Namespace): Command-line arguments containing
        configuration settings.

    Attributes:
        args (argparse.Namespace): The command-line arguments provided.
        vid_path (str): The path to the input video.
        iou_threshold (float): The iou threshold for tracking.
        score_threshold (float): The score confidence threshold for tracking.
        sort_tracker (Sort): An instance of the sorting algorithm used for tracking.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.vid_path = args.vid_path
        self.score_threshold = args.score_threshold
        self.iou_threshold = args.iou_threshold
        self.sort_tracker = Sort(
            max_age=args.max_age,
            min_hits=args.min_hits,
            iou_threshold=self.iou_threshold,
        )
        self.video_file_root = f"{Path(self.vid_path).stem}_"
        self.tracking_output_dir = Path("tracking_output")

    def load_trained_model(self) -> torch.nn.Module:
        """
        Load the trained model.

        Returns
        -------
        torch.nn.Module
        """
        model = torch.load(
            self.args.model_dir,
            map_location=torch.device(self.args.accelerator),
        )
        model.eval()
        return model

    def prep_sort(self, prediction):
        """
        Put predictions in format expected by SORT

        Parameters
        ----------
        prediction : dict
            The dictionary containing predicted bounding boxes, scores, and labels.

        Returns
        -------
        np.ndarray:
            An array containing sorted bounding boxes of detected objects.
        """
        pred_boxes = prediction[0]["boxes"].detach().cpu().numpy()
        pred_scores = prediction[0]["scores"].detach().cpu().numpy()
        pred_labels = prediction[0]["labels"].detach().cpu().numpy()

        pred_sort = []
        for box, score, label in zip(pred_boxes, pred_scores, pred_labels):
            if score > self.score_threshold:
                bbox = np.concatenate((box, [score]))
                pred_sort.append(bbox)

        return np.asarray(pred_sort)

    def load_video(self) -> None:
        """
        Load the input video, and prepare the output video if required.
        """
        # load trained model
        self.trained_model = self.load_trained_model()

        # load input video
        self.video = cv2.VideoCapture(self.vid_path)
        if not self.video.isOpened():
            raise Exception("Error opening video file")

        # read input video parameters
        frame_width = int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap_fps = self.video.get(cv2.CAP_PROP_FPS)

        # prepare output video writer if required
        if self.args.save_video or self.args.gt_dir:
            output_file = f"{self.video_file_root}output_video.mp4"
            output_codec = cv2.VideoWriter_fourcc(*"H264")
            self.out = cv2.VideoWriter(
                output_file, output_codec, cap_fps, (frame_width, frame_height)
            )

    def prep_csv_writer(self):
        """
        Prepare csv writer to output tracking results
        """
        self.tracking_output_dir.mkdir(parents=True, exist_ok=True)

        csv_file = open(
            str(self.tracking_output_dir / "tracking_output.csv"), "w"
        )
        csv_writer = csv.writer(csv_file)

        # write header following VIA convention
        # https://www.robots.ox.ac.uk/~vgg/software/via/docs/face_track_annotation.html
        csv_writer.writerow(
            (
                "filename",
                "file_size",
                "file_attributes",
                "region_count",
                "region_id",
                "region_shape_attributes",
                "region_attributes",
            )
        )

        return csv_writer, csv_file

    def write_bbox_to_csv(self, bbox, frame, frame_name, csv_writer):
        """
        Write bounding box annotation to csv
        """

        # Bounding box geometry
        xmin, ymin, xmax, ymax, id = bbox
        width_box = int(xmax - xmin)
        height_box = int(ymax - ymin)

        # Add to csv
        csv_writer.writerow(
            (
                frame_name,
                frame.size,
                '{{"clip":{}}}'.format("123"),
                1,
                0,
                '{{"name":"rect","x":{},"y":{},"width":{},"height":{}}}'.format(
                    xmin, ymin, width_box, height_box
                ),
                '{{"track":{}}}'.format(id),
            )
        )

    def get_ground_truth_data(self):
        # Initialize a list to store the extracted data
        ground_truth_data = []

        # Open the CSV file and read its contents line by line
        with open(self.args.gt_dir, "r") as csvfile:
            csvreader = csv.reader(csvfile)
            next(csvreader)  # Skip the header row
            for row in csvreader:
                # Extract relevant information from each row
                filename = row[0]
                region_shape_attributes = json.loads(row[5])
                region_attributes = json.loads(row[6])

                # Extract bounding box coordinates and object ID
                x = region_shape_attributes["x"]
                y = region_shape_attributes["y"]
                width = region_shape_attributes["width"]
                height = region_shape_attributes["height"]
                track_id = region_attributes["track"]

                # Compute the frame number from the filename
                frame_number = int(filename.split("_")[-1].split(".")[0])

                # Append the extracted data to the list
                ground_truth_data.append(
                    {
                        "filename": filename,
                        "frame_number": frame_number,
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                        "id": track_id,
                    }
                )
        return ground_truth_data

    def run_inference(self):
        """
        Run object detection + tracking on the video frames.
        """
        # Get transform to tensor
        transform = transforms.Compose([transforms.ToTensor()])

        # initialise frame counter
        frame_number = 1
        print(self.args.save_video)

        # initialise csv writer if required
        if self.args.save_csv_and_frames:
            csv_writer, csv_file = self.prep_csv_writer()

        if self.args.gt_dir:
            from crabs.detection_tracking.detection_utils import (
                draw_gt_tracking,
            )

            ground_truth_data = self.get_ground_truth_data()

        # loop thru frames of clip
        while self.video.isOpened():
            # break if beyond end frame (mostly for debugging)
            if self.args.max_frames_to_read:
                if frame_number > self.args.max_frames_to_read:
                    break

            # read frame
            ret, frame = self.video.read()
            if not ret:
                print("No frame read. Exiting...")
                break

            # run prediction
            img = transform(frame).to(self.args.accelerator)
            img = img.unsqueeze(0)
            prediction = self.trained_model(img)

            # run tracking
            pred_sort = self.prep_sort(prediction)
            tracked_boxes = self.sort_tracker.update(pred_sort)

            if self.args.gt_dir:
                gt_boxes = []
                for gt_data in ground_truth_data:
                    if gt_data["frame_number"] == frame_number:
                        gt_boxes.append(
                            (
                                gt_data["x"],
                                gt_data["y"],
                                gt_data["x"] + gt_data["width"],
                                gt_data["y"] + gt_data["height"],
                                gt_data["id"],
                            )
                        )
                gt_boxes = np.asarray(gt_boxes)
                frame_copy = frame.copy()
                frame_copy = draw_gt_tracking(
                    gt_boxes,
                    tracked_boxes,
                    frame_number,
                    self.iou_threshold,
                    frame_copy,
                )
                self.out.write(frame_copy)
                cv2.imshow("frame", frame_copy)
                if cv2.waitKey(30) & 0xFF == 27:
                    break

            # save tracking output (for manual labelling) if required
            if self.args.save_csv_and_frames:
                # loop thru tracked bounding boxes per frame
                for bbox in tracked_boxes:
                    # get frame name
                    frame_name = (
                        f"{self.video_file_root}frame_{frame_number:08d}.png"
                    )

                    # add bbox to csv
                    self.write_bbox_to_csv(bbox, frame, frame_name, csv_writer)

                    # save frame as png
                    frame_path = self.tracking_output_dir / frame_name
                    img_saved = cv2.imwrite(str(frame_path), frame)
                    if img_saved:
                        logging.info(
                            f"frame {frame_number} saved at {frame_path}"
                        )
                    else:
                        logging.info(
                            f"ERROR saving {frame_name}, frame {frame_number}"
                            "...skipping",
                        )
                        break

            # add each annotation to output video frame if required
            if self.args.save_video:
                frame_copy = frame.copy()
                for bbox in tracked_boxes:
                    xmin, ymin, xmax, ymax, id = bbox

                    # plot
                    draw_bbox(
                        frame_copy,
                        int(xmin),
                        int(ymin),
                        int(xmax),
                        int(ymax),
                        (0, 0, 255),
                        f"id : {int(id)}",
                    )

                self.out.write(frame_copy)

            # update frame
            frame_number += 1

        # Close input video
        self.video.release()

        # Close outputs
        if self.args.save_video or self.args.gt_dir:
            self.out.release()

        if args.save_csv_and_frames:
            csv_file.close()
        cv2.destroyAllWindows()


def main(args) -> None:
    """
    Main function to run the inference on video based on the trained model.

    Parameters
    ----------
    args : argparse
        Arguments or configuration settings for testing.

    Returns
    -------
        None
    """

    inference = DetectorInference(args)
    inference.load_video()
    inference.run_inference()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model_dir",
        type=str,
        required=True,
        help="location of trained model",
    )
    parser.add_argument(
        "--vid_path",
        type=str,
        required=True,
        help="location of images and coco annotation",
    )
    parser.add_argument(
        "--save_video",
        action="store_true",
        help="save video inference",
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default=os.getcwd(),
        help="location of output video",
    )
    parser.add_argument(
        "--score_threshold",
        type=float,
        default=0.1,
        help="threshold for prediction score",
    )
    parser.add_argument(
        "--iou_threshold",
        type=float,
        default=0.1,
        help="threshold for prediction score",
    )
    parser.add_argument(
        "--max_age",
        type=int,
        default=1,
        help="Maximum number of frames to keep alive a track without associated detections.",
    )
    parser.add_argument(
        "--min_hits",
        type=int,
        default=3,
        help="Minimum number of associated detections before track is initialised.",
    )
    parser.add_argument(
        "--accelerator",
        type=str,
        default="gpu",
        help="accelerator for pytorch lightning",
    )
    parser.add_argument(
        "--save_csv_and_frames",
        action="store_true",
        help=(
            "Save predicted tracks in VIA csv format and export corresponding frames. "
            "This is useful to prepare for manual labelling of tracks."
        ),
    )
    parser.add_argument(
        "--max_frames_to_read",
        type=int,
        default=None,
        help="Maximum number of frames to read (mostly for debugging).",
    )
    parser.add_argument(
        "--gt_dir",
        type=str,
        default=None,
        help="Directory contains ground truth annotations.",
    )
    args = parser.parse_args()
    main(args)

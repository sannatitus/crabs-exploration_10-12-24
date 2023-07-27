# -*- coding: utf-8 -*-
"""DRAFT_crabs.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1-XuJDgovJPX54qbaEnBzidV4dmMPsU1C

# 1. Clone the RAFT repo

# ---> run !git clone https://github.com/princeton-vl/RAFT.git

# ---> run !pip install pathlib

# 2. Install conda and dependencies

See:
https://inside-machinelearning.com/en/how-to-install-use-conda-on-google-colab/

Only base environment: https://github.com/conda-incubator/condacolab/tree/0.1.x

The code has been tested with PyTorch 1.6 and Cuda 10.1.

"""

# ---> run !pip install -q condacolab
# import condacolab

# condacolab.install()
# condacolab.check()

# ---> run !conda --version
# If !conda --version returns no results, install conda with :
# !pip install -q condacolab
# import condacolab
# condacolab.install()

# You can only update base virtual environment

# ---> run !conda env list

# ---> run !conda env update -n base -f environment.yml

# ---> run
# !conda install pytorch=1.6.0 torchvision=0.7.0 cudatoolkit=10.1
# matplotlib tensorboard scipy opencv -c pytorch

##################

# ---> run !conda list

# !conda install python=3.7 pytorch=1.6.0 -c pytorch

# !conda install opencv

# !conda install tensorboard scipy matplotlib

# !conda install cudatoolkit=10.1

# !conda install pytorch=1.6.0 torchvision=0.7.0 -c pytorch

# 3. Run inference

# Download pretrained models


# Commented out IPython magic to ensure Python compatibility.
# %%bash
# RAFT/download_models.sh

# Run inference on sequence of frames

# !python RAFT/demo.py --model=models/raft-kitti.pth --path=RAFT/demo-frames

# imports
import sys
import glob
import os
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
from PIL import Image

sys.path.append("RAFT/core")  # TODO: maybe not needed?

from RAFT.core.raft import RAFT  # noqa: E402
from RAFT.core.utils import flow_viz  # noqa: E402
from RAFT.core.utils.utils import InputPadder  # noqa: E402

print(torch.__version__)
print(torch.cuda.is_available())

# utils

DEVICE = "cuda"


def load_image(imfile):
    img = np.array(Image.open(imfile)).astype(np.uint8)
    img = torch.from_numpy(img).permute(2, 0, 1).float()
    return img[None].to(DEVICE)


def opencv_cap_to_torch_tensor(opencv_cap_frame):
    # opencv cap returns numpy array of size (h, w, channel)
    img = np.array(opencv_cap_frame).astype(
        np.uint8
    )  # TODO: it is already np.array do I need to make it np.unit8?
    img = torch.from_numpy(img).permute(2, 0, 1).float()
    return img[None].to(DEVICE)


# pil_img = Image.open('/content/RAFT/demo-frames/frame_0016.png')
# print(type(pil_img))
# img = np.array(pil_img).astype(np.uint8)
# print(img.shape) # height, width, channel


def viz(img, flo, img_filename):
    img = img[0].permute(1, 2, 0).cpu().numpy()  # BRG ---> RGB
    flo = flo[0].permute(1, 2, 0).cpu().numpy()

    # map flow to rgb image
    flo = flow_viz.flow_to_image(flo)
    img_flo = np.concatenate([img, flo], axis=1)

    plt.imshow(img_flo / 255.0)
    plt.show()

    # cv2.imshow(f'output/image_{c}.png', img_flo[:, :, [2,1,0]]/255.0)
    # cv2.waitKey()
    img_saved_bool = cv2.imwrite(
        f"output/flow_{Path(img_filename).name}", img_flo[:, :, [2, 1, 0]]
    )  # RGB ---> BRG
    if not img_saved_bool:
        print(f"Flow image for {Path(img_filename).name} not saved")


def demo(args):
    model = torch.nn.DataParallel(RAFT(args))
    model.load_state_dict(torch.load(args.model))

    model = model.module
    model.to(DEVICE)
    model.eval()

    with torch.no_grad():
        images = glob.glob(os.path.join(args.path, "*.png")) + glob.glob(
            os.path.join(args.path, "*.jpg")
        )

        images = sorted(images)
        for imfile1, imfile2 in zip(images[:-1], images[1:]):
            print(imfile1)
            image1 = load_image(imfile1)
            print(image1.shape)
            print(type(image1))
            image2 = load_image(imfile2)

            padder = InputPadder(image1.shape)
            image1, image2 = padder.pad(image1, image2)

            flow_low, flow_up = model(image1, image2, iters=20, test_mode=True)
            # TODO what is is flow_low: image in frame f+1 to image in frame f?
            viz(image1, flow_up, imfile1)


# def demo_video(args):
#     # initialise model
#     model = torch.nn.DataParallel(RAFT(args))
#     model.load_state_dict(torch.load(args.model))

#     model = model.module
#     model.to(DEVICE)
#     model.eval()

#     # initialise video capture
#     cap = cv2.VideoCapture(str(args.path))
#     nframes = cap.get(cv2.CAP_PROP_FRAME_COUNT)  # 9000
#     width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)  # 1920.0
#     height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)  # 1080.0
#     frame_rate = cap.get(cv2.CAP_PROP_FPS)  # 25fps

#     # initialise video writer
#     videowriter = cv2.VideoWriter(
#         f'{Path(args.path).stem}_flow.mp4',
#         cv2.VideoWriter_fourcc('m', 'p', '4', 'v'),
#         frame_rate,
#         (width, height)
#     )

#     with torch.no_grad():

#         # ensure we start capture at 0
#         if cap.get(cv2.CAP_PROP_POS_FRAMES) == 0:
#           frame_idx = cap.get(cv2.CV_CAP_PROP_POS_FRAMES)
#           print(frame_idx)

#           while frame_idx < nframes-1: # skip the last frame!
#             # set position (does this work?)---------------------
#             cap.set(cv2.CV_CAP_PROP_POS_FRAMES)

#             # read frame 1
#             success_frame_1, frame_1 = cap.read()
#             # set next starting position as frame 1
#             frame_idx = cap.get(cv2.CV_CAP_PROP_POS_FRAMES)
#             # read frame 2
#             success_frame_2, frame_2 = cap.read()

#             # frame_1 is <class 'numpy.ndarray'>
#             # shape (1080, 1920, 3)

#             # if at least one of them is not successfully read, exit
#             if not any([success_frame_1, success_frame_2]):
#                 print(
#                       "At least one frame was not read correctly. Exiting ...
#                   ")
#                 break


#             # make them torch tensors
#             image1 = opencv_cap_to_torch_tensor(frame_1)
#             # torch tensor of torch.Size([1, 3, 436, 1024]) (h x w)
#             image2 = opencv_cap_to_torch_tensor(frame_2)

#             # pad images (why?)---------
#             padder = InputPadder(image1.shape)
#             image1, image2 = padder.pad(image1, image2)

#             # compute flow
#             flow_low, flow_up = model(
#                   image1, image2, iters=20, test_mode=True
#             )

#             # save to writer
#             img = image1[0].permute(1,2,0).cpu().numpy() # BRG ---> RGB
#             flo = flow_up[0].permute(1,2,0).cpu().numpy()

#             # map flow to rgb image
#             flo = flow_viz.flow_to_image(flo)
#             img_flo = np.concatenate([img, flo], axis=1)

#             videowriter.write(img_flo[:, :, [2,1,0]]) # RGB ---> BRG

#             # # TODO what is is flow_low:
#             # image in frame f+1 to image in frame f?
#             # viz(image1, flow_up, imfile1)


# https://stackoverflow.com/questions/2352181/how-to-use-a-dot-to-access-members-of-dictionary
class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


# simulate arg parse
args = {
    "model": "models/raft-kitti.pth",
    "path": "RAFT/demo-frames",
    "small": False,
    "mixed_precision": False,
    "alternate_corr": False,
}

args = dotdict(args)

# ---> run !mkdir output
demo(args)

# ---> run !rm -r /content/output/

#############

# simulate arg parse
args = {
    "model": "models/raft-kitti.pth",
    "path": "/content/NINJAV_S001_S001_T003_subclip.mp4",
    "small": False,
    "mixed_precision": False,
    "alternate_corr": False,
}

args = dotdict(args)

# initialise model
model = torch.nn.DataParallel(RAFT(args))
model.load_state_dict(torch.load(args.model))  # type: ignore[attr-defined]

model = model.module
model.to(DEVICE)
model.eval()

# initialise video capture
cap = cv2.VideoCapture(str(args.path))  # type: ignore[attr-defined]

nframes = cap.get(cv2.CAP_PROP_FRAME_COUNT)  # 9000
width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)  # 1920.0
height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)  # 1080.0
frame_rate = cap.get(cv2.CAP_PROP_FPS)  # 25fps

# initialise video writer
videowriter = cv2.VideoWriter(
    f"{Path(args.path).stem}_flow.mp4",  # type: ignore[attr-defined]
    cv2.VideoWriter_fourcc("m", "p", "4", "v"),
    frame_rate,
    tuple(int(x) for x in (width, height)),
)

# mmmm quite slow.....
with torch.no_grad():
    # ensure we start capture at 0
    if cap.get(cv2.CAP_PROP_POS_FRAMES) == 0:
        frame_idx = 0

        while frame_idx < nframes - 1:  # skip the last frame!
            # set position to the desired index
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            print(f"focus frame: {cap.get(cv2.CAP_PROP_POS_FRAMES)}")

            # read frame 1
            success_frame_1, frame_1 = cap.read()
            # the index to read next is now at frame 2,
            # set it as the next starting position
            frame_idx = cap.get(cv2.CAP_PROP_POS_FRAMES)
            # read frame 2
            success_frame_2, frame_2 = cap.read()

            # if at least one of them is not successfully read, exit
            if not any([success_frame_1, success_frame_2]):
                print("At least one frame was not read correctly. Exiting ...")
                break

            # make them torch tensors
            image1 = opencv_cap_to_torch_tensor(frame_1)
            # In example:
            # output is torch tensor of torch.Size([1, 3, 436, 1024])
            # (h x w)
            image2 = opencv_cap_to_torch_tensor(frame_2)

            # pad images (why?)---------
            padder = InputPadder(image1.shape)
            image1, image2 = padder.pad(image1, image2)

            # compute flow
            # output has batch channel on the first dim
            flow_low, flow_up = model(image1, image2, iters=20, test_mode=True)

            # convert output to numpy array and reorder channels
            img = image1[0].permute(1, 2, 0).cpu().numpy()  # c,h,w --> h,w, c
            flo = flow_up[0].permute(1, 2, 0).cpu().numpy()

            # map flow to rgb image
            flo = flow_viz.flow_to_image(flo)
            # img_flo = np.concatenate([img, flo], axis=1)
            # print(type(flo)) # numpy array

            videowriter.write(flo[:, :, [2, 1, 0]])  # BRG ---> RGB

cap.release()
videowriter.release()
cv2.destroyAllWindows()

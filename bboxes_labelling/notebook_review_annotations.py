# %%
import matplotlib.pyplot as plt
import json

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Review annotations combined

with open(
    "/Users/sofia/Desktop/crabs_annotations_backup/NW/COCO_combined.json", "r"
) as f:
    labelled_data = json.load(f)

print(f"N images: {len(labelled_data['images'])}")
print(f"N annotations: {len(labelled_data['annotations'])}")

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#
# map image ids to filename
map_image_ids_to_name = {im["id"]: im["file_name"] for im in labelled_data["images"]}

# lists of image ID, name and frame nr per annotation
list_image_ids_per_annotation = [an["image_id"] for an in labelled_data["annotations"]]
list_image_name_per_annotation = [
    map_image_ids_to_name[id] for id in list_image_ids_per_annotation
]
list_frame_number_per_annotation = [
    int(im.rpartition("_")[-1].split(".")[0]) for im in list_image_name_per_annotation
]

# list of video name per image
list_video_name_per_image = [
    img_name.rpartition("_")[0] for img_name in map_image_ids_to_name.values()
]

# map video names to int
map_video_names_to_int = {
    video_name: idx
    for idx, video_name in enumerate(sorted(list(set(list_video_name_per_image))))
}


# %%
# plot frame number vs annotation ID
# annotations are sorted in increasing frame number per video
plt.figure()
plt.plot(list_frame_number_per_annotation)
plt.xlabel("annotation ID")
plt.ylabel("frame number")
# %%
# plot histogram
edges = list(range(0, len(map_image_ids_to_name.keys()) + 1))
edges_hist = [ed + 0.5 for ed in edges]
plt.figure()
n_annotations_per_img, bins, patches = plt.hist(
    list_image_ids_per_annotation, bins=edges_hist
)
plt.xlabel("image ID")
plt.ylabel("n labelled crabs (annotations)")
# %% plot scatter, color by video
plt.figure()
plt.scatter(
    x=map_image_ids_to_name.keys(),
    y=n_annotations_per_img,
    c=[map_video_names_to_int[x] for x in list_video_name_per_image],
)
plt.xlabel("image ID")
plt.ylabel("n labelled crabs (annotations)")
# %% plot per video


plt.figure()
for p in range(0, len(n_annotations_per_img), 50):
    plt.plot(
        n_annotations_per_img[p : p + 50], ".-", label=list_video_name_per_image[p]
    )
# plt.show()
plt.xlabel("increasing frame number ->")
plt.ylabel("n labelled crabs (annotations)")
plt.xticks([])
plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
# %%

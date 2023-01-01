import sys, os, random
import shutil
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import argparse

# argparse
parser = argparse.ArgumentParser(description='Copy images into folders based on aspect ratio.')
parser.add_argument('image-directory')
parser.add_argument('-o', '--output-directory', default="")
parser.add_argument('--min-height', default=256, type=int)
parser.add_argument('--max-height', default=1024, type=int)
parser.add_argument('--min-width', default=256, type=int)
parser.add_argument('--max-width', default=1024, type=int)
parser.add_argument('--step', default=64, type=int)
parser.add_argument('--max-pixel-count', default=512*512, type=int)
args = parser.parse_args()

jpeg_quality = 100
class Buckets:
    def __init__(self,
        dst_path="",
        min_height=256,
        max_height=1024,
        min_width=256,
        max_width=1024,
        step=64,
        max_pixel_count=512*768
        ):
        self.buckets = [[512, 512]]
        for width in range(min_width, max_width, step):
            h = max(filter(lambda x: x*width <= max_pixel_count, range(min_height, max_height+1, step)))
            if not [width, h] in self.buckets:
                self.buckets.append([width,h])
            if not [h, width] in self.buckets:
                self.buckets.append([h,width])
        self.buckets.sort(key=lambda x: (x[0], x[0]/x[1]))
        self.aspects = list(map(lambda x: x[0]/x[1], self.buckets))

        if dst_path and not dst_path.endswith(('\\','/')):
            dst_path = dst_path + '/'

        self.dst_path = dst_path

    def get_bucket_size(self, size):
        aspect = size[0]/size[1]
        idx = min(map(lambda x: [abs(x[1]-aspect), x[0]], enumerate(self.aspects)), key=lambda x:x[0])[1]
        return self.buckets[idx]

    def get_bucket_dir_name(self, width, height):
        return f'{self.dst_path}{width}x{height}'
    
    def get(self):
        return self.buckets

buckets = Buckets(
    dst_path = args.output_directory,
    min_height = args.min_height,
    max_height = args.max_height,
    min_width = args.min_width,
    max_width = args.max_width,
    step = args.step,
    max_pixel_count = args.max_pixel_count)

# create dir
for width, height in buckets.get():
    os.makedirs(buckets.get_bucket_dir_name(width, height), exist_ok=True)

def process_image(args):
    filepath, buckets = args
    im = Image.open(filepath)

    # scale
    bw, bh = buckets.get_bucket_size(im.size)
    w, h = im.size
    scale_factor = max(bw/w, bh/h)
    w, h = round(w*scale_factor), round(h*scale_factor)
    im = im.resize((w, h), Image.Resampling.LANCZOS)

    # random crop
    crop_pixel = max(w-bw, h-bh)
    if crop_pixel != 0:
        crop_ofs = random.randrange(0, crop_pixel)
        if w-bw > h-bh:
            # width crop
            im = im.crop((0+crop_ofs, 0, w - (crop_pixel-crop_ofs), h))
        else:
            # height crop
            im = im.crop((0, 0+crop_ofs, w , h - (crop_pixel-crop_ofs)))

    bucket_dir_name = buckets.get_bucket_dir_name(im.width, im.height)
    im.save(f'{bucket_dir_name}/{os.path.basename(filepath)}', quality=jpeg_quality)

    # copy tag file
    tag_file = f"{os.path.splitext(os.path.basename(filepath))[0]}.txt"
    tag_path = f"{os.path.dirname(filepath)}/{tag_file}"
    if os.path.isfile(tag_path):
        shutil.copyfile(tag_path, f"{bucket_dir_name}/{tag_file}")

with ThreadPoolExecutor(max_workers=os.cpu_count()) as thread_pool:
    import glob
    files = glob.glob(f"{sys.argv[1]}/**/*.[jp][pn][g]", recursive=True)
    thread_pool.map(process_image, [(file, buckets) for file in files])

# delete empty dir
for width, height in buckets.get():
    name = buckets.get_bucket_dir_name(width, height)
    if not os.listdir(name):
        os.rmdir(name)
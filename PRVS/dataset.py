import os
import glob
import scipy
import torch
import random
import numpy as np
import torchvision.transforms.functional as F
from torch.utils.data import DataLoader
from PIL import Image
from scipy.misc import imread
from skimage.feature import canny
from skimage.color import rgb2gray


class Dataset(torch.utils.data.Dataset):
    def __init__(self, opt, flist, edge_flist, mask_flist, augment=True, training=True, mask_reverse = False):
        super(Dataset, self).__init__()
        self.augment = augment
        self.training = training
        self.data = self.load_flist(flist)
        self.edge_data = self.load_flist(edge_flist)
        self.mask_data = self.load_flist(mask_flist)

        self.input_size = opt.img_size
        self.sigma = opt.sigma
        self.mask = opt.mask
        self.mask_reverse = mask_reverse

        # in test mode, there's a one-to-one relationship between mask and image
        # masks are loaded non random
        if opt.mask_mode == 2:
            self.mask = 6

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        try:
            item = self.load_item(index)
        except:
            print('loading error: ' + self.data[index])
            item = self.load_item(0)

        return item

    def load_name(self, index):
        name = self.data[index]
        return os.path.basename(name)

    def load_item(self, index):

        size = self.input_size
        
        # load image
        img = imread(self.data[index])
        
        # resize/crop if needed
        if size != 0:
            img = self.resize(img, size, size)
        # create grayscale image
        img_gray = rgb2gray(img)
        
        # load mask
        mask = self.load_mask(img, index)
        
        # load edge
        edge = self.load_edge(img_gray, index, mask)

        # augment data
        if self.augment and np.random.binomial(1, 0.5) > 0:
            img = img[:, ::-1, ...]
            img_gray = img_gray[:, ::-1, ...]
            edge = edge[:, ::-1, ...]
            mask = mask[:, ::-1, ...]
        if self.training:
            return self.to_tensor(img), self.to_tensor(img_gray), self.to_tensor(edge), self.to_tensor(mask)
        else:
            return self.to_tensor(img), self.to_tensor(img_gray), self.to_tensor(edge)*self.to_tensor(mask), self.to_tensor(mask)

    def load_edge(self, img, index, mask):
        sigma = self.sigma

        # in test mode images are masked (with masked regions), 
        # using 'mask' parameter prevents canny to detect edges for the masked regions
        # canny 
        if sigma == -1:
            return np.zeros(img.shape).astype(np.float)
        
        # random sigma
        if sigma == 0:
            sigma = random.randint(1, 4)
        return canny(img, sigma=sigma).astype(np.float)

    def load_mask(self, img, index):
        imgh, imgw = img.shape[0:2]
        mask_type = self.mask
        # external + random block
        # external
        if mask_type == 0:
            mask_index = random.randint(0, len(self.mask_data) - 1)
            mask = imread(self.mask_data[mask_index])
            mask = self.resize(mask, imgh, imgw)

            mask = (mask > 0).astype(np.uint8)       # threshold due to interpolation
            if self.mask_reverse:
                return (1 - mask) * 255
            else:
                return mask * 255

    def to_tensor(self, img):
        img = Image.fromarray(img)
        img_t = F.to_tensor(img).float()
        return img_t

    def resize(self, img, height, width, centerCrop=True):
        imgh, imgw = img.shape[0:2]

        if centerCrop and imgh != imgw:
            # center crop
            side = np.minimum(imgh, imgw)
            j = (imgh - side) // 2
            i = (imgw - side) // 2
            img = img[j:j + side, i:i + side, ...]

        img = scipy.misc.imresize(img, [height, width])

        return img

    def load_flist(self, flist):
        if isinstance(flist, list):
            return flist

        # flist: image file path, image directory path, text file flist path
        if isinstance(flist, str):
            if flist[-3:] == "txt":
                line = open(flist,"r")
                lines = line.readlines()
                file_names = []
                for line in lines:
                    file_names.append("../../Dataset/Places2/train/data_256"+line.split(" ")[0])
                return file_names
            if os.path.isdir(flist):
                flist = list(glob.glob(flist + '/*.jpg')) + list(glob.glob(flist + '/*.png'))
                flist.sort()
                return flist

            if os.path.isfile(flist):
                try:
                    return np.genfromtxt(flist, dtype=np.str, encoding='utf-8')
                except:
                    return [flist]

        return []

    def create_iterator(self, batch_size):
        while True:
            sample_loader = DataLoader(
                dataset=self,
                batch_size=batch_size,
                drop_last=True
            )

            for item in sample_loader:
                yield item

def create_mask(width, height, mask_width, mask_height, x=None, y=None):
    mask = np.zeros((height, width))
    mask_x = x if x is not None else random.randint(0, width - mask_width)
    mask_y = y if y is not None else random.randint(0, height - mask_height)
    mask[mask_y:mask_y + mask_height, mask_x:mask_x + mask_width] = 1
    return mask
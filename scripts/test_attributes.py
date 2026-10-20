from virtual_closet.config import ROOT
from virtual_closet.images import read_image
from virtual_closet.model import FashionModel

if __name__ == '__main__':
    model = FashionModel()
    for path in sorted((ROOT/'picture'/'sample_pics').glob('*')):
        if path.suffix.lower() not in {'.jpg','.jpeg','.png','.webp'}:
            continue
        print('\nImage:',path.name)
        result = model.analyze(read_image(path.read_bytes()))
        for name, candidates in result['rankings'].items():
            print(name+':',' > '.join(candidates))

from threading import RLock
import json
import torch
from transformers import CLIPModel, CLIPProcessor
from .config import MODEL_ID
from .attributes import CATEGORIES, COLORS, BASE_PATTERNS, DECORATIONS, SUBCATEGORIES

class FashionModel:
    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.lock = RLock()
        self.processor = CLIPProcessor.from_pretrained(MODEL_ID, use_fast=False)
        self.model = CLIPModel.from_pretrained(MODEL_ID, use_safetensors=True).to(self.device).eval()
        self.text_cache = {}

    def text_features(self, prompts):
        key = tuple(prompts)
        with self.lock, torch.inference_mode():
            if key not in self.text_cache:
                inputs = self.processor(text=list(prompts), return_tensors='pt', padding=True,
                    truncation=True, max_length=self.model.config.text_config.max_position_embeddings).to(self.device)
                features = self.model.get_text_features(**inputs)
                self.text_cache[key] = torch.nn.functional.normalize(features, dim=-1).cpu()
            return self.text_cache[key]

    def image_features(self, image):
        with self.lock, torch.inference_mode():
            inputs = self.processor(images=image, return_tensors='pt').to(self.device)
            features = self.model.get_image_features(**inputs)
            return torch.nn.functional.normalize(features, dim=-1).cpu()[0]

    @staticmethod
    def _rank(labels, features, embedding):
        scores = features @ embedding
        return [labels[i] for i in scores.topk(min(3, len(labels))).indices.tolist()]

    def rank(self, embedding, candidates):
        labels = list(candidates)
        return self._rank(labels, self.text_features(list(candidates.values())), embedding)

    def analyze(self, image):
        embedding = self.image_features(image)
        category_ranks = self.rank(embedding, CATEGORIES)
        category = category_ranks[0]
        subs = {s: f'a photo of {s}' for s in SUBCATEGORIES[category]}
        subs['Other / unspecified'] = f'a photo of a {category.lower()}'
        groups = {
            'Subcategory': subs,
            'Color': {c: f'a photo of a predominantly {c.lower()} {category.lower()}' for c in COLORS},
            'Base pattern': {k: f'a photo of a {category.lower()} whose main outer fabric is {v}' for k,v in BASE_PATTERNS.items()},
            'Decoration': {k: f'a photo of a {category.lower()} with {v}' for k,v in DECORATIONS.items()},
        }
        flat_labels, flat_prompts, spans = [], [], {}
        for name, candidates in groups.items():
            start = len(flat_labels)
            flat_labels.extend(candidates)
            flat_prompts.extend(candidates.values())
            spans[name] = (start, len(flat_labels))
        features = self.text_features(flat_prompts)
        rankings = {'Category': category_ranks}
        for name, (start, end) in spans.items():
            rankings[name] = self._rank(flat_labels[start:end], features[start:end], embedding)
        return {'attributes': {k:v[0] for k,v in rankings.items()},
                'rankings': rankings, 'embedding': embedding.tolist()}

    def occasion_scores(self, items, occasion):
        vectors = torch.tensor([json.loads(i['embedding_json']) for i in items], dtype=torch.float32)
        query = self.text_features([f'a photo of clothing for {occasion}'])[0]
        return {item['id']: float(score) for item,score in zip(items, vectors @ query)}


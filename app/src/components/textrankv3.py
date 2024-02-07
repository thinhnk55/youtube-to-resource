import string
import time
from typing import List, Tuple

from dataclasses import dataclass
from nltk import sent_tokenize
import numpy as np
import spacy
import networkx as nx

# nltk.download('words')
# nltk.download('maxent_ne_chunker')
# nltk.download('wordnet')
# nltk.download('averaged_perceptron_tagger')
# nltk.download('puntk')

def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]

def clean(text):
    # text = text.lower()
    escape_chars = ['\n', '\t', '\v', '\b', '\r', '\f', '\a', '\\']
    for c in escape_chars:
        text = text.replace(c, '')
    printable = set(string.printable)
    text = ''.join(list(filter(lambda x: x in printable, text)))
    return text

keep_pos = ['NOUN', 'ADJ', 'VERB']

verb_phrases = [('AUX', 'VERB', 'ADP'), 
                ('VERB', 'PART', 'VERB'), 
                ('VERB', 'ADP'),
                ]

@dataclass(frozen=True)
class Lemma:
    lemma: str
    pos: str

    def __repr__(self) -> str:
        return f'{self.lemma} - {self.pos}'

@dataclass
class Token():
    text: str
    lemma: str
    pos: str
    tag: str
    dep: str
    sent: int
    i: int
    id: int

    def __hash__(self) -> int:
        return self.id + hash(self)

    def __repr__(self) -> str:
        rep = f'{self.text}:\n'
        rep += f'\tLemma: {self.lemma}\n'
        rep += f'\tPOS: {self.pos}\n'
        rep += f'\tTAG: {self.tag}\n'
        rep += f'\tDEP: {self.dep}'
        return rep

@dataclass
class Word():
    text: str
    tokens: List[Token]
    root: Token
    span: Tuple[int, int]
    sent: int

    def __repr__(self) -> str:
        return self.text

@dataclass
class Sentence():
    text: str
    words: List[Word]
    tokens: List[Token]
    id: int

    def __init__(self, text, pos, spacy_model):
        self.text = text
        self.id = pos
        self.spacy_model = spacy_model
        self.__build()

    def __build(self):
        doc = self.spacy_model(self.text)
        tokens = self.__extract_token(doc)
        chunks = self.__extract_chunks(doc)
        words = self.__process_chunk(chunks, tokens)
        self.tokens = tokens
        self.words = self.__filter_words(words)


    def __check_range(self, i, idx_range):
        for s, e, _ in idx_range:
            if (i >= s) and (i < e):
                return False
        return True
    
    def __extract_chunks(self, doc):
        chunks = []
        for token in doc.noun_chunks:
            chunks.append((token.start, token.end, token.root.i))
        # for token in doc.ents:
        #     chunks.append((token.start, token.end, token.root.i))
        return chunks

    def __len__(self):
        return len(self.tokens)
    
    def __filter_words(self, words):
        def filter_fn(x):
            if len(x.tokens) == 1 and x.root.pos not in keep_pos:
                return False
            if x.root.pos not in keep_pos:
                return False
            return True
        return list(filter(filter_fn, words))
    
    def __process_chunk(self, chunks, tokens):
        words = [Word(' '.join([t.text for t in tokens[s:e]]), tokens[s:e], tokens[r], (s, e), self.id) for s, e, r in chunks]
        to = set([t.i for w in words for t in w.tokens])
        for t in tokens:
            if t.i not in to:
                words.append(Word(t.text, [t], t, (t.i, t.i + 1), self.id))
        return list(sorted(words, key=lambda x:x.span[0]))

    def __process_possible_chunk(self, token, doc):
        possible_chunk_start = token.i
        for pattern in verb_phrases:
            curr_pt = token.i
            flag = True
            if token.pos_ == pattern[0]:
                for pattern_idv in pattern[1:]:
                    curr_pt += 1
                    if doc[curr_pt].pos_ != pattern_idv:
                        flag = False
                        break
                if flag:
                    curr_pt += 1
                    root = possible_chunk_start
                    for i in range(possible_chunk_start, curr_pt):
                        if doc[i].pos_ == 'VERB':
                            root = i
                    return (possible_chunk_start, curr_pt, root)

        return None
    
    def __extract_token(self, doc):
        tokens = [Token(token.text, token.lemma_, token.pos_, token.tag_, token.dep_, self.id, token.i, token.i + self.id) for token in doc]
        return tokens
    
    def __repr__(self) -> str:
        return self.text

@dataclass
class Vocab():
    text: str
    root: str
    pos: str
    score: float
    occurence: List[Word]

    def __repr__(self) -> str:
        rep = f'{self.text}:\n'
        rep += f'\tRoot: {self.root}\n'
        rep += f'\tPOS: {self.pos}\n'
        rep += f'\tScore: {self.score}\n'
        rep += f'\tOccurenece (sentence id): {[o.sent for o in self.occurence]}'
        return rep

@dataclass
class Dictionary():
    vocab: List[Vocab]

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.vocab[key]
        if isinstance(key, str):
            for i, v in enumerate(self.vocab):
                if v.text == key:
                    return self.vocab[i]
                
    def __len__(self):
        return len(self.vocab)
                
    def contains(self, text):
        for v in self.vocab:
            if v.text == text:
                return True
        return False
    
    def append(self, text, word):
        root = word.root.lemma
        pos = word.root.pos
        if self.contains(text):
            if self[text].root == root:
                count = 0
                for t in self[text].occurence:
                    if root == t.root.lemma and pos == t.root.pos:
                        count += 1
                if len(self[text].occurence) // 2 < count:
                    self[text].root = root
                    self[text].pos = pos
            self[text].occurence.append(word)
        else:
            self.vocab.append(Vocab(text, root, pos, 0.0, [word]))

    def __repr__(self) -> str:
        rep = ''
        for i, v in enumerate(self.vocab):
            rep += f'({i}): {repr(v)}\n'
        return rep
            
    
class Doc():
    def __init__(self, window_size=3, epochs=10, threshold=1e-5, d=0.85, lim_phrases=10):
        self.window_size = window_size
        self.epochs = epochs
        self.threshold = threshold
        self.d = d
        self.lim_phrases = lim_phrases
        self.nlp = spacy.load('en_core_web_sm')
        self.run_time = 0.0
        self.sents = []
        self.__w = []
        self.vocab = []
        self.g = nx.Graph()

    def __split(self, text):
        sents = sent_tokenize(text)
        pos = 0
        res_sents = []
        for sent in sents:
            new_sent = Sentence(sent, pos, self.nlp)
            pos += 1
            res_sents.append(new_sent)
        return res_sents
    
    def __get_w(self):
        self.__w = [
            [w for w in sent.words] for sent in self.sents
        ]

    def __get_nodes(self):
        nodes = [
            Lemma(token.lemma, token.pos)
            for sent in self.__w
            for word in sent
            for token in word.tokens
            if token.pos in keep_pos
        ]

        return nodes

    def __get_edges(self):
        edges = []
        
        for sent in self.__w:
            h = [
                Lemma(token.lemma, token.pos)
                for word in sent
                for token in word.tokens
                if token.pos in keep_pos
            ]

            for hop in range(self.window_size):
                for idx, node in enumerate(h[:-1-hop]):
                    edges.append((node, h[idx + hop + 1]))
            
        counter = {}
        for u, v in edges:
            if (u, v) in counter:
                counter[(u,v )] += 1
            else:
                counter[(u, v)] = 1       
        return [(u, v, {'weight': w * 1.0}) for (u, v), w in counter.items()]
    
    def __create_graph(self, nodes, edges):
        self.g.add_nodes_from(nodes)
        self.g.add_edges_from(edges)

    def __get_scores(self):
        rank = self.__rank
        kws = []
        for w in [word for sent in self.__w for word in sent]:
            score = 0
            non_lemma = 0
            for t in w.tokens:
                key = Lemma(t.lemma, t.pos)
                s = rank.get(key, 0)
                if s == 0:
                    non_lemma += 1
                else:
                    if t.text != t.lemma:
                        non_lemma += 1
                score += s
            n = len(w.tokens)
            discount = n / (n + (2.0 * non_lemma) + 1.0)
            kws.append((w, score * discount))
        return kws
    
    def __process_res(self, kws):
        processed = {}
        for kw, s in kws:
            if kw.text not in processed:
                processed[kw.text] = {
                    'words': [kw],
                    'score': s
                }
            else:
                processed[kw.text]['words'].append(kw)
        return {k:v for k, v in sorted(processed.items(), key=lambda item:item[1]['score'], reverse=True)}

    def fit(self, text):
        t0 = time.time()

        self.sents = self.__split(text)
        self.__get_w()
        nodes = self.__get_nodes()
        edges = self.__get_edges()
        self.__create_graph(nodes, edges)
        self.__rank = nx.pagerank(self.g)
        kws = self.__get_scores()
        self.vocab = self.__process_res(kws)
        self.top_sents_ids = self.__calc_sent_dist()

        self.run_time = time.time() - t0

    def __calc_base_vec(self, n):
        vec = np.array([kws['score'] for _, kws in self.vocab.items()])[:n]
        vec_len = vec.sum(0)
        if vec_len != 0:
            vec /= vec_len
        return vec
    
    def __calc_sent_dist(self):
        n = self.lim_phrases
        unit_vec = self.__calc_base_vec(n)

        sent_mat = np.zeros((len(self.sents), n))
        
        for i, (_, v) in enumerate(list(self.vocab.items())[:n]):
            s = v['score']
            for occr in v['words']:
                sent_mat[occr.sent][i] = s

        np.square((unit_vec - sent_mat), sent_mat)
        sent_mat = np.sum(sent_mat, 1)
        np.sqrt(sent_mat, sent_mat)
        sents = [(i, s) for i, s in enumerate(sent_mat)]
        return sorted(sents, key=lambda x:x[1], reverse=True)
    
    def __extract_top_sents(self, num_sents, preserved):
        def calc_optimal_num_sents():
            # mean = sum([s[1] for s in self.top_sents_ids]) / len(self.top_sents_ids)
            # counter = 0
            # for _, s in self.top_sents_ids:
            #     if s >= mean:
            #         counter += 1
            # return counter

            return int(len(self.sents) * (1/4))
        
        if num_sents == 0:
            num_sents = calc_optimal_num_sents()
        
        if preserved:
            return [self.sents[i] for i, _ in sorted(self.top_sents_ids, key=lambda x:x[0])[:num_sents]]
        else:
            return [self.sents[i] for i, _ in self.top_sents_ids]

    def summarize(self, lim_sents=4, preserved=True):
        sents = self.__extract_top_sents(lim_sents, preserved)
        return ' '.join([s.text for s in sents])
    
    def get_sents_in_batch(self, batch=32):
        return batch(self.sents, batch) if self.sents else None
    
    def __extract_roots(self, sent):
        ws = []
        for w in sent.words:
            ws.append(w.root.i)
        return ws

    def __build_questions(self, sent_id):
        sent = self.sents[sent_id]
        roots = self.__extract_roots(sent)
        qs = []
        for rid in roots:
            text = []
            for t in sent.tokens:
                if t.i == rid:
                    text.append('___')
                else:
                    text.append(t.text)
            qs.append((' '.join(text), sent.tokens[rid].text, sent.tokens[rid].pos))
        return qs
            
    
    def gen_questions(self):
        return {i:self.__build_questions(i) for i, _ in self.top_sents_ids}
    
    def get_lemmas(self):
        return self.__rank.items()

"""
TODO:
    - Keywords Extraction (Done) - Still need improved
    - Summarize (Done) - Optimize auto num sents
    - Question auto generating (Done) - Need more optimizations and improvements and filters and solve the comma space thingy
    - Definition ()
    - Extract Cefr level ()
"""
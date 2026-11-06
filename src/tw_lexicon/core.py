"""Dictionary ingestion, pronunciation parsing, and filtering."""
import json
import pickle
import re
from collections import defaultdict
from pathlib import Path
import pandas as pd
import yaml

INITIALS = dict(zip('ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙ', ['b','p','m','f','d','t','n','l','g','k','h','j','q','x','zh','ch','sh','r','z','c','s']))
MEDIALS = {'ㄧ':'i', 'ㄨ':'u', 'ㄩ':'ü'}
FINALS = dict(zip('ㄚㄛㄜㄝㄞㄟㄠㄡㄢㄣㄤㄥㄦ', ['a','o','e','ê','ai','ei','ao','ou','an','en','ang','eng','er']))
TONES = {'ˊ':2, 'ˇ':3, 'ˋ':4, '˙':5}

def parse_zhuyin(value, pinyin=''):
    text = str(value or '').strip().replace(' ', '')
    tone_marks = [TONES[c] for c in text if c in TONES]
    symbols = ''.join(c for c in text if c not in TONES)
    initial = INITIALS.get(symbols[:1], '')
    if initial: symbols = symbols[1:]
    medial = MEDIALS.get(symbols[:1], '')
    if medial: symbols = symbols[1:]
    remainder = FINALS.get(symbols, '') if symbols else ''
    valid = bool(text) and len(tone_marks) <= 1 and (not symbols or bool(remainder)) and bool(medial or remainder or initial in ('zh','ch','sh','r','z','c','s'))
    coda = 'ng' if remainder.endswith('ng') else 'n' if remainder.endswith('n') else ''
    nucleus = remainder[:-len(coda)] if coda else remainder
    if not nucleus: nucleus = medial if not coda else ''
    if medial and not remainder: medial = ''
    if not nucleus and initial in ('zh','ch','sh','r','z','c','s'): nucleus = 'apical'
    phon_final = medial + nucleus + coda
    # Orthographic spelling is retained, including diacritics, for traceability.
    orth = re.sub(r'^[bpmfdtnlgkhjqx]|^(zh|ch|sh|r|z|c|s)', '', str(pinyin or ''), flags=re.I)
    return {'initial':initial, 'medial':medial, 'nucleus':nucleus, 'coda':coda, 'phonological_final':phon_final, 'orthographic_final':orth, 'tone':tone_marks[0] if tone_marks else 1, 'parse_status':'ok' if valid else 'review'}

def broad_pos(pos):
    pos = str(pos or '')
    return {'N':'noun','V':'verb','A':'adjective','D':'adverb'}.get(pos[:1].upper(), 'other')

def load_config(path):
    with open(path, encoding='utf8') as f: return yaml.safe_load(f)

def cwn_senses(path):
    # The distributed image is a pickle: only load trusted, official files.
    with open(path, 'rb') as f: vertices, edges, *_ = pickle.load(f)
    result = defaultdict(list)
    for (src, dst), edge in edges.items():
        if edge.get('edge_type') != 'has_sense': continue
        lemma, sense = vertices.get(src, {}), vertices.get(dst, {})
        word = lemma.get('lemma', '')
        if len(word) != 1 or sense.get('node_type') != 'sense': continue
        pos = sense.get('pos', '')
        result[word].append({'sense_id':dst, 'cwn_pos':pos, 'broad_pos':broad_pos(pos), 'definition':sense.get('def',''), 'examples':sense.get('examples',[])})
    return result

def build(config):
    ds = config['datasets']
    senses = cwn_senses(ds['cwn'])
    df = pd.read_excel(ds['moe'], dtype=str, keep_default_na=False)
    rows = []
    for source in df.to_dict('records'):
        word = str(source.get('字詞名','')).strip()
        if len(word) != 1: continue
        eid = str(source.get('字詞號','')).strip().strip('"')
        readings = [(source.get('注音一式',''), source.get('漢語拼音',''), 'main')]
        if source.get('變體注音'): readings.append((source['變體注音'], source.get('變體漢語拼音',''), 'variant'))
        for zhuyin, pinyin, kind in readings:
            for sense in senses.get(word, [None]):
                row = {'character':word, 'entry_id':eid, 'zhuyin':zhuyin, 'pinyin':pinyin, 'reading_type':kind, 'moe':source, 'sense_match_status':'review' if sense else 'no_cwn_sense', 'independent_word_status':'review', 'moe_version':ds['moe_version'], 'cwn_version':ds['cwn_version']}
                row.update(parse_zhuyin(zhuyin, pinyin)); row.update(sense or {})
                rows.append(row)
    path = Path(config['processed']); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf8')
    return rows

def load_rows(config):
    return json.loads(Path(config['processed']).read_text(encoding='utf8'))

def filtered(rows, config, overrides=None):
    f = dict(config.get('filters', {})); f.update({k:v for k,v in (overrides or {}).items() if v is not None})
    initial = set(f.get('initials', [])); finals = set(f.get('finals', []))
    for name in f.get('initial_presets', []): initial.update(config['phonology']['initial_presets'][name])
    presets = [config['phonology']['final_presets'][x] for x in f.get('final_presets', [])]
    pos_key = 'cwn_pos' if f.get('pos_granularity') == 'fine' else 'broad_pos'
    def match(r):
        final_match = not finals and not presets or r['phonological_final'] in finals or any(all(r.get(k) in v for k,v in p.items()) for p in presets)
        return (not initial or r['initial'] in initial) and final_match and (not f.get('tones') or r['tone'] in f['tones']) and (not f.get('pos') or r.get(pos_key) in f['pos']) and (not f.get('require_cwn_sense') or bool(r.get('sense_id')))
    return [r for r in rows if match(r)]

def minimal_sets(rows, require_four=True, granularity='broad'):
    groups = defaultdict(lambda: defaultdict(list)); poskey = 'cwn_pos' if granularity == 'fine' else 'broad_pos'
    for row in rows:
        if row.get('parse_status') != 'ok' or not row.get(poskey) or row['tone'] not in (1,2,3,4): continue
        groups[(row['initial'], row['phonological_final'], row[poskey])][row['tone']].append(row)
    result = []
    for (initial, final, pos), tones in sorted(groups.items()):
        if require_four and len(tones) != 4: continue
        result.append({'initial':initial, 'phonological_final':final, 'pos':pos, 'complete':len(tones)==4, 'status':'sense and independent-word review', **{f'tone_{n}':tones.get(n,[]) for n in range(1,5)}})
    return result

"""Command-line and interactive interfaces."""
import json
import shutil
import wave
from pathlib import Path
import pandas as pd
import typer
from rich.console import Console
from .core import build, filtered, load_config, load_rows, minimal_sets

app = typer.Typer(no_args_is_help=True)
datasets = typer.Typer(); audio = typer.Typer()
app.add_typer(datasets, name='datasets'); app.add_typer(audio, name='audio')
console = Console()

def cfg(path): return load_config(path)
def split(value): return [x.strip() for x in value.split(',') if x.strip()] if value is not None else None

def export(rows, path, formats):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    # Remove only files this export owns, including formats disabled since the last run.
    for suffix in ('csv', 'json', 'xlsx'):
        path.with_suffix('.' + suffix).unlink(missing_ok=True)
    for fmt in formats:
        dest = path.with_suffix('.' + fmt)
        if fmt == 'json': dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf8')
        elif fmt in ('csv', 'xlsx'):
            tabular = rows
            if fmt == 'xlsx' and rows and 'tone_1' in rows[0]:
                tabular = []
                for group in rows:
                    for n in range(1, 5):
                        for candidate in group.get(f'tone_{n}', []):
                            tabular.append({**{k: v for k, v in group.items() if not k.startswith('tone_')}, 'set_tone': n, **candidate})
            data = [{k:json.dumps(v, ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in tabular]
            frame = pd.DataFrame(data)
            if fmt == 'csv': frame.to_csv(dest, index=False, encoding='utf-8-sig')
            else: frame.to_excel(dest, index=False)
        else: raise ValueError(f'Unsupported export format: {fmt}')
        console.print(f'Wrote {dest}')

def export_sets(rows, path, formats):
    export(rows, path, formats)
    dest = Path(path).with_name('simplified.tsv')
    columns = ['initial', 'phonological_final', 'pos', 't1', 't2', 't3', 't4']
    simplified = []
    for group in rows:
        item = {key: group[key] for key in columns[:3]}
        for tone in range(1, 5):
            item[f't{tone}'] = ', '.join(sorted({r['character'] for r in group.get(f'tone_{tone}', []) if r.get('character')}))
        simplified.append(item)
    pd.DataFrame(simplified, columns=columns).to_csv(dest, sep='\t', index=False, encoding='utf-8')
    console.print(f'Wrote {dest}')

def clear_copied_audio(c):
    directory = (Path(c['output_dir']) / 'audio' / 'wav').resolve()
    manifest_path = Path(c['output_dir']) / 'audio' / 'manifest.json'
    if not manifest_path.is_file():
        return
    for row in json.loads(manifest_path.read_text(encoding='utf8')):
        if row.get('copied_to'):
            path = Path(row['copied_to']).resolve()
            if path.parent == directory:
                path.unlink(missing_ok=True)

def input_rows(path):
    path = Path(path)
    if path.suffix == '.json': return json.loads(path.read_text(encoding='utf8'))
    if path.suffix == '.csv': return pd.read_csv(path, dtype=str, keep_default_na=False).to_dict('records')
    raise ValueError('Input must be JSON or CSV')

def flatten(rows):
    result = []
    for row in rows:
        if 'character' in row: result.append(row); continue
        for n in range(1,5):
            values = row.get(f'tone_{n}', [])
            if isinstance(values, str): values = json.loads(values) if values else []
            result.extend(values)
    return result

@datasets.command('setup')
def setup(config: str = 'config/default.yaml'):
    try:
        rows = build(cfg(config)); console.print(f'Built {len(rows)} pronunciation/sense records')
    except (OSError, ValueError, KeyError) as exc: raise typer.BadParameter(str(exc)) from exc

@app.command()
def search(config: str = 'config/default.yaml', initials: str = None, finals: str = None, initial_preset: str = None, final_preset: str = None, tones: str = None, pos: str = None):
    c = cfg(config)
    overrides = {'initials':split(initials), 'finals':split(finals), 'initial_presets':split(initial_preset), 'final_presets':split(final_preset), 'tones':[int(x) for x in split(tones)] if tones is not None else None, 'pos':split(pos)}
    rows = filtered(load_rows(c), c, overrides)
    console.print(f'{len(rows)} records'); export(rows, Path(c['output_dir'])/'candidates'/'results', c['export']['formats'])

@app.command('minimal-sets')
def sets(config: str = 'config/default.yaml', initials: str = None, pos: str = None, require_four_tones: bool = True):
    c = cfg(config); rows = filtered(load_rows(c), c, {'initials':split(initials), 'pos':split(pos)})
    result = minimal_sets(rows, require_four_tones, c['filters'].get('pos_granularity','broad'))
    console.print(f'{len(result)} sets'); export_sets(result, Path(c['output_dir'])/'minimal_sets'/'results', c['export']['formats'])

def audio_rows(c, records, copy=False):
    ds = c['datasets']; index = pd.read_excel(ds['audio_index'], dtype=str, keep_default_na=False)
    lookup = {}
    for entry in index.to_dict('records'):
        lookup.setdefault((str(entry['字詞號']).strip().strip('"'), str(entry['字詞名']).strip()), []).append(entry['檔案名稱'])
    out = []; seen = set(); dest = Path(c['output_dir'])/'audio'/'wav'
    for row in flatten(records):
        key = (str(row.get('entry_id','')), str(row.get('character','')), str(row.get('zhuyin','')))
        if key in seen: continue
        seen.add(key); names = lookup.get(key[:2], [])
        item = {'entry_id':key[0], 'character':key[1], 'zhuyin':key[2], 'pinyin':row.get('pinyin',''), 'tone':row.get('tone',''), 'source_version':ds['moe_version'], 'recording_type':'dictionary entry narration', 'pronunciation_match':'review', 'status':'missing' if not names else 'ambiguous' if len(names)>1 else 'found', 'source_filename':'', 'path':''}
        if len(names) == 1:
            name = str(names[0]); path = Path(ds['audio_dir']) / name
            item.update(source_filename=name, path=str(path))
            if not path.is_file(): item['status'] = 'missing_file'
            else:
                try:
                    with wave.open(str(path), 'rb') as wav:
                        item.update(sample_rate=wav.getframerate(), channels=wav.getnchannels(), duration_seconds=wav.getnframes()/wav.getframerate(), format='wav')
                except (wave.Error, EOFError): item['status'] = 'invalid_wav'
                if copy and item['status'] == 'found':
                    dest.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest/name); item['copied_to'] = str(dest/name)
        out.append(item)
    return out

@audio.command('manifest')
def manifest(input: str = typer.Option(...), config: str = 'config/default.yaml'):
    c=cfg(config); records=input_rows(input); clear_copied_audio(c); rows=audio_rows(c,records); export(rows, Path(c['output_dir'])/'audio'/'manifest', ['csv','json'])

@audio.command('extract')
def extract(input: str = typer.Option(...), config: str = 'config/default.yaml'):
    c=cfg(config); records=input_rows(input); clear_copied_audio(c); rows=audio_rows(c,records, True); export(rows, Path(c['output_dir'])/'audio'/'manifest', ['csv','json'])

@app.command()
def tui(config: str = 'config/default.yaml'):
    c=cfg(config)
    console.print('Available initial presets: ' + ', '.join(c['phonology']['initial_presets']))
    console.print('Available final presets: ' + ', '.join(c['phonology']['final_presets']))
    initial=typer.prompt('Initials (comma separated)', default='', show_default=False)
    ip=typer.prompt('Initial presets (comma separated)', default='', show_default=False)
    final=typer.prompt('Finals (comma separated)', default='', show_default=False)
    fp=typer.prompt('Final presets (comma separated)', default='', show_default=False)
    tones=typer.prompt('Tones (comma separated)', default='1,2,3,4')
    pos=typer.prompt('POS (comma separated)', default='', show_default=False)
    rows=filtered(load_rows(c), c, {'initials':split(initial), 'finals':split(final), 'initial_presets':split(ip), 'final_presets':split(fp), 'tones':[int(x) for x in split(tones)], 'pos':split(pos)})
    groups=minimal_sets(rows, True, c['filters'].get('pos_granularity','broad'))
    console.print(f'{len(rows)} records; {len(groups)} complete four-tone sets')
    if typer.confirm('Export results?', default=True):
        export(rows, Path(c['output_dir'])/'candidates'/'results', c['export']['formats']); export_sets(groups, Path(c['output_dir'])/'minimal_sets'/'results', c['export']['formats'])
    if typer.confirm('Check audio availability?', default=False):
        matches=audio_rows(c, rows); console.print(f"{sum(x['status']=='found' for x in matches)} recordings found of {len(matches)} entries")
        if typer.confirm('Export audio manifest?', default=True):
            clear_copied_audio(c)
            export(matches, Path(c['output_dir'])/'audio'/'manifest', ['csv','json'])

if __name__ == '__main__': app()

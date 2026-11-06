from tw_lexicon.core import parse_zhuyin, filtered, minimal_sets, cwn_senses
from tw_lexicon.cli import audio_rows
import pickle
import pandas as pd

def test_parse():
    assert parse_zhuyin('ㄑㄩˊ')['phonological_final'] == 'ü'
    assert parse_zhuyin('ㄧㄢˇ')['coda'] == 'n'
    assert parse_zhuyin('ㄨㄤˋ')['initial'] == ''
    assert parse_zhuyin('ㄅ?')['parse_status'] == 'review'

def test_filters_and_sets():
    config={'filters':{'require_cwn_sense':True}, 'phonology':{'initial_presets':{'s':['q','x']}, 'final_presets':{'nasal':{'coda':['n','ng']}}}}
    rows=[dict(initial='q', phonological_final='ian', coda='n', tone=n, broad_pos='verb', sense_id=str(n), parse_status='ok') for n in range(1,5)]
    selected=filtered(rows, config, {'initial_presets':['s'], 'final_presets':['nasal']})
    assert len(selected)==4
    assert minimal_sets(selected)[0]['complete']
    assert not minimal_sets(selected[:3])
    assert not minimal_sets(selected[:3], False)[0]['complete']

def test_cwn_graph(tmp_path):
    p=tmp_path/'graph'; pickle.dump(({'l':{'lemma':'字'},'s':{'node_type':'sense','pos':'Na','def':'meaning'}},{('l','s'):{'edge_type':'has_sense'}},{}),p.open('wb'))
    assert cwn_senses(p)['字'][0]['sense_id']=='s'

def test_audio_missing(tmp_path):
    index=tmp_path/'index.xlsx'; pd.DataFrame([{'字詞號':'0001','字詞名':'八','檔案名稱':'0001.wav'}]).to_excel(index,index=False)
    c={'datasets':{'audio_index':str(index),'audio_dir':str(tmp_path),'moe_version':'v'},'output_dir':str(tmp_path)}
    rows=audio_rows(c,[{'entry_id':'0001','character':'八','zhuyin':'ㄅㄚ'}])
    assert rows[0]['status']=='missing_file'
    assert rows[0]['pronunciation_match']=='review'

def test_simplified_export_and_stale_formats(tmp_path):
    from tw_lexicon.cli import export_sets
    path = tmp_path / 'results'
    path.with_suffix('.xlsx').write_text('old')
    groups = [{'initial':'q', 'phonological_final':'i', 'pos':'verb', 'tone_1':[{'character':'欺'}, {'character':'欺'}, {'character':'期'}], 'tone_2':[{'character':'騎'}], 'tone_3':[], 'tone_4':[{'character':'棄'}]}]
    export_sets(groups, path, ['json'])
    assert not path.with_suffix('.xlsx').exists()
    result = pd.read_csv(tmp_path/'simplified.tsv', sep='\t', keep_default_na=False)
    assert result.loc[0, 't1'] == '期, 欺'
    assert result.loc[0, 't3'] == ''
    export_sets([], path, ['json'])
    assert len(pd.read_csv(tmp_path/'simplified.tsv', sep='\t')) == 0

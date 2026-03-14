import pytest

from cmate.parser import Parser
from cmate.visitor import InfoCollector, Evaluator


@pytest.fixture(scope='session')
def parser():
    return Parser()


@pytest.fixture()
def info_collector():
    return InfoCollector()


def test_collect_given_metadata_name_assignment_when_input_is_valid_then_extract_correct_metadata_info(parser, info_collector):
    text = '''\
[metadata]
name = 'test_name'
---
'''
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {'contexts': {}, 'metadata': {'name': 'test_name'}, 'targets': {}}


def test_parse_multiple_metadata_blocks_when_later_block_overrides_earlier_one(parser, info_collector):
    text = '''\
[metadata]
name = 'test_1'
---

[metadata]
name = 'test_2'
---
'''
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {'contexts': {}, 'metadata': {'name': 'test_2'}, 'targets': {}}


def test_collect_when_given_par_env_with_assert_in_desc_then_par_env_parsed_as_target(parser, info_collector):
    text = '''\
[par env]
assert 1, ''
'''
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        'metadata': {},
        'targets':
            {
                'env': {'desc': None, 'parse_type': None, 'required_targets': None, 'required_contexts': None}
            },
        'contexts': {}
    }


def test_collect_when_multiple_par_blocks_present_then_all_blocks_parsed_as_targets(parser, info_collector):
    text = '''\
[par env]
assert 1, ''

[par sys]
assert 1, ''
'''
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        'metadata': {},
        'targets':
            {
                'env': {'desc': None, 'parse_type': None, 'required_targets': None, 'required_contexts': None},
                'sys': {'desc': None, 'parse_type': None, 'required_targets': None, 'required_contexts': None}
            },
        'contexts': {}
    }


def test_collect_when_target_requires_context_then_context_and_target_relation_captured(parser, info_collector):
    text = '''\
[par env]
assert ${context::a} == 2, ''

'''
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        'metadata': {},
        'targets': {
            'env': {'desc': None, 'parse_type': None, 'required_targets': None, 'required_contexts': ['a']}
        },
        'contexts': {'a': {'desc': None, 'options': [2]}}
    }


def test_collect_when_same_target_with_different_context_options_then_options_merged_in_context(parser, info_collector):
    text = '''\
[par env]
assert ${context::a} == 2, ''
---
[par env]
assert ${context::a} == 3, ''
'''
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        'metadata': {},
        'targets': {
            'env': {'desc': None, 'parse_type': None, 'required_targets': None, 'required_contexts': ['a']}
        },
        'contexts': {'a': {'desc': None, 'options': [2, 3]}}
    }


def test_collect_when_target_defined_in_dependency_block_then_parse_type_and_desc_parsed_correctly(parser, info_collector):
    text = '''\
[dependency]
sys : 'System' @ 'json'
---

[par sys]
assert ${env::ABC} == ${context::test}, 'test'
'''
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        'metadata': {},
        'targets':
            {
                'sys': {'desc': 'System', 'parse_type': 'json', 'required_targets': ['env'], 'required_contexts': ['test']}
            },
        'contexts': {}
    }


def test_collect_complex_scenario_with_metadata_dependency_and_conditional_logic_then_info_collected_correctly(parser, info_collector):
    text = '''\
[metadata]
name = 'MindIE 配置项检查'
authors = [{"name": "a", "email": "b"}, {"name": "c"}]
---

[dependency]
mies_config: 'MindIE Service 主配置文件' @ 'json'
deploy_mode: '部署模式标识，用于确定检查规则集'
---

[global]
if ${context::deploy_mode} == 'pd_mix':
    dp = ${mies_config::BackendConfig.ModelDeployConfig.ModelConfig[0].dp} or 1
    
    if ${context::model_type} == 'deepseek':
        moe_ep = ${mies_config::BackendConfig.ModelDeployConfig.ModelConfig[0].moe_ep} or 1
    fi
fi
---

[par mies_config]
if ${context::deploy_mode} == 'pd_mix':
    assert ${pp} == 1, 'pp 取值只能等于 1', error
fi
'''
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        'metadata': {'name': 'MindIE 配置项检查', 'authors': [{'name': 'a', 'email': 'b'}, {'name': 'c'}]},
        'targets': {'mies_config': {'desc': 'MindIE Service 主配置文件', 'parse_type': 'json', 'required_targets': None, 'required_contexts': ['deploy_mode']}},
        'contexts': {'deploy_mode': {'desc': ('部署模式标识，用于确定检查规则集', None), 'options': ['pd_mix']}}
    }


@pytest.fixture()
def evaluator():
    return Evaluator()


def test_a(parser, evaluator):
    ''''''
import pytest

from caiman.documents.models import AccessLabel, canonical_json


def test_missing_and_dropped_labels_fail_closed():
    assert not AccessLabel().permits({'alpha'})
    assert not AccessLabel(False, frozenset()).permits({'alpha'})
    assert not AccessLabel(False, frozenset({'alpha', 'beta'})).permits({'alpha'})
    assert not AccessLabel(False, frozenset({'a'})).permits('alpha')


def test_labels_share_prefixing_and_subset_semantics():
    label = AccessLabel(False, frozenset({'alpha'}))
    assert label.prefixed_labels() == frozenset({'compartment:alpha'})
    assert label.permits({'alpha', 'beta'})
    assert AccessLabel(True).permits(set())


@pytest.mark.parametrize('label', [lambda: AccessLabel(True, frozenset({'alpha'})),
                                  lambda: AccessLabel(False, frozenset({'../alpha'}))])
def test_ambiguous_or_unsafe_labels_rejected(label):
    with pytest.raises(ValueError):
        label()


def test_canonical_json():
    assert canonical_json({'b': 1, 'a': 'é'}) == '{"a":"é","b":1}'.encode()

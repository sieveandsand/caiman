import pytest
from caiman.documents.models import canonical_json
from caiman.storage.store import Store


def test_canonical_json():
    assert canonical_json({'b': 1, 'a': 'é'}) == '{"a":"é","b":1}'.encode()


def test_pods_are_local_folders_not_authorization(tmp_path):
    store = Store(tmp_path)
    store.pods.ensure('alpha')
    assert store.pods.selected() == {'public', 'alpha'}
    assert store.pods.selected(['alpha']) == {'alpha'}
    store.pods.set_default('alpha')
    assert store.pods.default == 'alpha'


@pytest.mark.parametrize('name', ['../alpha', '', '/tmp/alpha', 'a/b'])
def test_invalid_pod_paths_are_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        Store(tmp_path).pods.ensure(name)


def test_pod_identity_survives_folder_rename(tmp_path):
    store = Store(tmp_path)
    store.pods.ensure('alpha')
    (tmp_path / 'alpha').rename(tmp_path / 'renamed')
    assert store.pod_path('alpha') == tmp_path / 'renamed'

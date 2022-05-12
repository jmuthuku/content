from QualysCreateIncidentFromReport import get_asset_id_for_ip
import demistomock as demisto


def test_get_asset_id_for_ip(mocker):
    with open('test_data/qualys_host_list_rawresponse.xml') as f:
        raw_response = f.read()
    mocker.patch.object(demisto, 'executeCommand',
                        return_value=[{'Contents': raw_response, 'Type': 'note'}])
    assert '69291564' == get_asset_id_for_ip('1.1.1.1')

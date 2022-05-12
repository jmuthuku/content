import demistomock as demisto
from QualysCreateIncidentFromReport import main, get_asset_id_for_ip


def test_main(mocker):
    with open('test_data/qualys_host_list_rawresponse.xml') as f:
        raw_response = f.read()
    mocker.patch.object(demisto, 'args', return_value=dict())
    mocker.patch.object(demisto, 'getFilePath',
                        return_value={'id': id, 'path': 'test_data/test_report.xml', 'name': 'test_report.xml'})
    mocker.patch.object(demisto, 'executeCommand',
                        side_effect=[[{'Contents': raw_response, 'Type': 'notes'}],
                                     [{"Contents": {"total": 1}, 'Type': 'notes'}]])
    demisto_results = mocker.spy(demisto, 'results')
    main()
    demisto_results.assert_called_once_with("Done.")


def test_get_asset_id_for_ip(mocker):
    with open('test_data/qualys_host_list_rawresponse.xml') as f:
        raw_response = f.read()
    mocker.patch.object(demisto, 'executeCommand', return_value=[{'Contents': raw_response, 'Type': 'note'}])
    assert '69291564' == get_asset_id_for_ip('1.1.1.1')

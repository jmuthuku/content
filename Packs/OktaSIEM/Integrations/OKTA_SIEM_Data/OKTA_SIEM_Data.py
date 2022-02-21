from CommonServerPython import *

# IMPORTS
# Disable insecure warnings
requests.packages.urllib3.disable_warnings()

# CONSTANTS
DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
SEARCH_LIMIT = 200
PROFILE_ARGS = [
    'firstName',
    'lastName',
    'email',
    'login',
    'secondEmail',
    'middleName',
    'honorificPrefix',
    'honorificSuffix',
    'title',
    'displayName',
    'nickName',
    'profileUrl',
    'primaryPhone',
    'mobilePhone',
    'streetAddress',
    'city',
    'state',
    'zipCode',
    'countryCode',
    'postalAddress',
    'preferredLanguage',
    'locale',
    'timezone',
    'userType',
    'employeeNumber',
    'costCenter',
    'organization',
    'division',
    'department',
    'managerId',
    'manager'
]


class Client(BaseClient):
    """
    Client will implement the service API, and should not contain any Demisto logic.
    Should only do requests and return data.
    """

    def __init__(self, base_url: str, verify: bool, first_fetch: str, api_token: str, proxy: bool,
                 fetch_limit: str):
        self.first_fetch = arg_to_datetime(first_fetch).isoformat()
        self.fetch_limit = arg_to_number(fetch_limit)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'SSWS {api_token}'
        }
        ok_codes = (200, 201, 204)
        super().__init__(base_url=base_url, verify=argToBoolean(verify), headers=headers, proxy=argToBoolean(proxy),
                         ok_codes=ok_codes)

    @staticmethod
    def should_reset_list(previous_fetch_time: str, new_fetch_time:str):
        # if the newest event in our last fetch is grater by at least a second we are guaranteed that the previous
        # events that were saved will no longer be needed to be saved to check for duplicates
        return arg_to_datetime(new_fetch_time.split('.')[0]) > arg_to_datetime(previous_fetch_time.split('.')[0])


    @staticmethod
    def get_readable_logs(raw_logs):
        logs = []
        raw_logs = raw_logs if isinstance(raw_logs, list) else [raw_logs]
        for log in raw_logs:
            if log.get('client', {}).get('userAgent'):
                browser = log.get('client', {}).get('userAgent').get('browser')
                if (not browser) or browser.lower() == 'unknown':
                    browser = 'Unknown browser'
                os = log.get('client', {}).get('userAgent').get('os')
                if (not os) or os.lower() == 'unknown':
                    os = 'Unknown OS'
                device = log.get('client', {}).get('device')
            if (not device) or device.lower() == 'unknown':
                device = 'Unknown device'
            targets = ''
            if log.get('target'):
                for target in log.get('target'):
                    targets += f"{target.get('displayName')} ({target.get('type')})\n"
            time_published = datetime.strptime(log.get('published'), '%Y-%m-%dT%H:%M:%S.%f%z').strftime("%m/%d/%Y, "
                                                                                                        "%H:%M:%S")
            log = {
                'Actor': f"{log.get('actor', {}).get('displayName')} ({log.get('actor', {}).get('type')})",
                'ActorAlternaneId': log.get('actor', {}).get('alternateId'),
                'EventInfo': log.get('displayMessage'),
                'EventOutcome': log.get('outcome', {}).get('result') + (
                    f": {log.get('outcome', {}).get('reason')}" if log.get('outcome', {}).get('reason') else ''),
                'EventSeverity': log.get('severity'),
                'Client': f"{browser} on {os} {device}",
                'RequestIP': log.get('client', {}).get('ipAddress'),
                'ChainIP': [ip_chain.get('ip') for ip_chain in log.get('request', {}).get('ipChain', [])],
                'Targets': targets or '-',
                'Time': time_published
            }
            logs.append(log)
        return logs

    def get_paged_results(self, uri, query_param=None):
        response = self._http_request(
            method="GET",
            url_suffix=uri,
            resp_type='response',
            params=query_param
        )
        paged_results = response.json()
        while "next" in response.links and len(response.json()) > 0:
            next_page = response.links.get("next").get("url")
            response = self._http_request(
                method="GET",
                full_url=next_page,
                url_suffix='',
                resp_type='response',
                params=query_param

            )
            paged_results += response.json()
        return paged_results

    def get_logs(self, params):
        uri = 'logs'
        query_params = {}
        for key, value in params.items():
            if key == 'query':
                key = 'q'
            query_params[key] = encode_string_results(value)
        # if args.get('limit'):
        #     return self._http_request(
        #         method='GET',
        #         url_suffix=uri,
        #         params=query_params
        #     )
        return self.get_paged_results(uri, query_params)

    def fetch_logs(self):
        new_last_run = last_run = demisto.getLastRun()
        fetch_start_time = last_run.get('last_event_created_time') or self.first_fetch
        previous_fetched_uuids = last_run.get('previous_fetched_uuids') or []

        params = {
            'limit': str(self.fetch_limit),
            'since': fetch_start_time
        }

        sorted_events_to_save = []
        res = self.get_logs(params)
        if res:
            new_events = []
            new_events_uuids = []
            for item in res:
                if item_uuid := item.get('uuid') not in previous_fetched_uuids:
                    new_events.append(item)
                    new_events_uuids.append(item_uuid)

            # OKTA doesn't sort events by milliseconds so we sort the list before returning.
            sorted_events_to_save = sorted(new_events, key=lambda obj: arg_to_datetime(obj.get('published')))
            last_event_created_time = sorted_events_to_save[-1].get('published')

            if not self.should_reset_list(fetch_start_time, last_event_created_time):
                new_events_uuids = previous_fetched_uuids + new_events_uuids

            new_last_run = {
                'last_event_created_time': last_event_created_time,
                'previous_fetched_uuids': new_events_uuids
            }

        return sorted_events_to_save, new_last_run

def test_module(client, args):
    """
    Returning 'ok' indicates that the integration works like it is supposed to. Connection to the service is successful.

    Args:
        client: HelloWorld client

    Returns:
        'ok' if test passed, anything else will fail the test.
    """
    args
    uri = 'users/me'
    client._http_request(method='GET', url_suffix=uri)
    return CommandResults('ok')


def fetch_logs_command(client):
    logs = raw_response = client.fetch_logs()

    if not raw_response:
        return 'No logs found', {}, raw_response

    readable_output = tableToMarkdown('Okta Events', logs)
    outputs = {
        'Okta.Logs.Events(val.uuid && val.uuid === obj.uuid)': createContext(raw_response)
    }
    return (
        readable_output,
        outputs,
        raw_response
    )


def get_logs_command(client, args):
    logs = raw_response = client.get_logs(args)
    if not raw_response:
        return 'No logs found', {}, raw_response

    # logs = client.get_readable_logs(raw_response)
    readable_output = tableToMarkdown('Okta Events', logs)
    outputs = {
        'Okta.Logs.Events(val.uuid && val.uuid === obj.uuid)': createContext(raw_response)
    }
    return (
        readable_output,
        outputs,
        raw_response
    )


def main():
    """
        PARSE AND VALIDATE INTEGRATION PARAMS
    """
    try:
        # get the service API url

        params = demisto.params()
        base_url = urljoin(params.get('url'), '/api/v1/')
        api_token = params.get('apitoken')
        first_fetch = params.get('first_fetch', '3 days')
        fetch_limit = params.get('limit', 500)
        verify_certificate = not params.get('insecure', False)
        proxy = params.get('proxy', False)

        command = demisto.command()
        LOG(f'Command being called is {command}')

        client = Client(
            base_url=base_url,
            verify=verify_certificate,
            first_fetch=first_fetch,
            api_token=api_token,
            fetch_limit=fetch_limit,
            proxy=proxy)
        args = demisto.args()

        if command is 'test_module':
            return_results(test_module(client))

        elif command is 'fetch-incidents':
            return_results(fetch_logs_command(client))

        elif command is 'okta-get-logs':
            return_results(get_logs_command(client, args))

    # Log exceptions
    except Exception as e:
        return_error(f'Failed to execute {demisto.command()} command. Error: {str(e)}')


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()

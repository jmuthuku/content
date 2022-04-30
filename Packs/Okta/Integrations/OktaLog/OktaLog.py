from enum import Enum
from pydantic import BaseModel, AnyUrl, Json
from CommonServerPython import *


class Method(str, Enum):
    """
    A list that represent the types of http request available
    """
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    HEAD = 'HEAD'
    PATCH = 'PATCH'
    DELETE = 'DELETE'


class ReqParams(BaseModel):
    """
    A class that stores the request query params
    """
    since: str
    sortOrder: Optional[str] = 'ASCENDING'
    limit: str = '100'

    def set_since_value(self, since: 'dateTime as ISO string') -> None:
        self.since = since


class Request(BaseModel):
    """
    A class that stores a request configuration
    """
    method: Method
    url: AnyUrl
    headers: Optional[Union[Json[dict], dict]]
    params: Optional[ReqParams]
    verify = True
    data: Optional[str] = None


class Client:
    """
    A class for the client request handling
    """

    def __init__(self, request: Request):
        self.request = request

    def call(self, requests=requests) -> requests.Response:
        try:
            response = requests.request(**self.request.dict())
            response.raise_for_status()
            return response
        except Exception as exc:
            msg = f'something went wrong with the http call {exc}'
            LOG(msg)
            raise DemistoException(msg) from exc

    def set_next_run_filter(self, after: str):
        self.request.params.set_since_value(after)


class GetEvents:
    """
    A class to handle the flow of the integration
    """
    def __init__(self, client: Client) -> None:
        self.client = client

    def _iter_events(self, last_object_ids: list) -> None:
        """
        Function that responsible for the iteration over the events returned from the Okta api
        """
        response = self.client.call()
        events: list = response.json()
        if last_object_ids:
            events = GetEvents.remove_duplicates(events, last_object_ids)
        if len(events) == 0:
            return []
        while True:
            yield events
            last = events.pop()
            self.client.set_next_run_filter(last['published'])
            response = self.client.call()
            events: list = response.json()
            try:
                events.pop(0)
                assert events
            except (IndexError, AssertionError):
                LOG('empty list, breaking')
                break

    def aggregated_results(self, last_object_ids: List[str] = None) -> List[dict]:
        """
        Function to group the events according to the user limits
        """
        stored_events = []
        for events in self._iter_events(last_object_ids):
            stored_events.extend(events)
        return stored_events

    @staticmethod
    def get_last_run(events: List[dict]) -> dict:
        """
        Get the info from the last run, it returns the time to query from and a list of ids to prevent duplications
        """

        ids = []
        # gets the last event time
        last_time = events[-1].get('published')
        for event in events:
            if event.get('published') == last_time:
                ids.append(event.get('uuid'))
        last_time = datetime. strptime(str(last_time).lower().replace('z', ''), '%Y-%m-%dt%H:%M:%S.%f')
        return {'after': last_time.isoformat(), 'ids': ids}

    @staticmethod
    def remove_duplicates(events: list, ids: list) -> list:
        """
        Remove object duplicates by the uuid of the object
        """

        duplicates_indexes = []
        for i in range(len(events)):
            event_id = events[i]['uuid']
            if event_id in ids:
                duplicates_indexes.append(i)
        if len(duplicates_indexes) > 0:
            for i in duplicates_indexes:
                del events[i]
        return events


def main():
    # Args is always stronger. Get last run even stronger
    demisto_params = demisto.params() | demisto.args() | demisto.getLastRun()
    request_size = demisto_params.get('request_size', 2000)
    try:
        request_size = int(request_size)
    except ValueError:
        request_size = 2000
    after = int(demisto_params['after'])
    headers = json.loads(demisto_params['headers'])
    encrypted_headers = json.loads(demisto_params['encrypted_headers'])
    demisto_params['headers'] = dict(encrypted_headers.items() | headers.items())
    del demisto_params['encrypted_headers']
    last_run = demisto.getLastRun()
    last_object_ids = last_run.get('ids')
    # If we do not have an after in the last run than we calculate after according to now - after param from integration settings.
    if 'after' not in last_run:
        delta = datetime.today() - timedelta(days=after)
        last_run = delta.isoformat()
    else:
        last_run = last_run['after']
    demisto_params['params'] = ReqParams(**demisto_params, since=last_run)

    request = Request(**demisto_params)

    client = Client(request)

    get_events = GetEvents(client)

    command = demisto.command()
    if command == 'test-module':
        get_events.aggregated_results()
        demisto.results('ok')
    elif command == 'okta-get-events' or command == 'fetch-events':
        # Get the events from the api according to limit and request_size
        events = get_events.aggregated_results(last_object_ids=last_object_ids)
        if events:
            demisto.setLastRun(GetEvents.get_last_run(events))
            if command == 'fetch-events':
                while len(events) > 0:
                    send_events_to_xsiam(events[:request_size], 'okta', 'okta')
                    events = events[request_size:]
            elif command == 'okta-get-events':
                command_results = CommandResults(
                    readable_output=tableToMarkdown('Okta Logs', events, headerTransform=pascalToSpace),
                    outputs_prefix='Okta.Logs',
                    outputs_key_field='published',
                    outputs=events,
                    raw_response=events,
                )
                return_results(command_results)


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()

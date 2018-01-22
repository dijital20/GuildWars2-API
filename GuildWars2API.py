import logging

from json import JSONDecodeError, loads
from pprint import pformat
from urllib.parse import urlencode
from urllib.request import Request, HTTPError, URLError, urlopen


# Module level log.
MODULE_LOG = logging.getLogger('GuildWars2API')
MODULE_LOG.setLevel(logging.DEBUG)
# File Handler
file_handler = logging.FileHandler(
    'GuildWars2API.log', mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s - %(name)s - %(message)s'
))
MODULE_LOG.addHandler(file_handler)


class AuthorizationRequiredError(Exception):
    pass


class APIError(Exception):
    pass


class GW2APISession(object):
    _base_url = 'https://api.guildwars2.com'

    def __init__(self):
        self.__token = None
        self.token_info = None
        self._log.debug(f'Initialized {repr(self)}')

    def __repr__(self):
        state = 'Unauthenticated' \
            if self.token_info is None \
            else f'Authenticated with {str(self.token_info)}'
        return f'<{self.__class__.__name__} {state}>'

    @property
    def token(self):
        return self.__token

    @token.setter
    def token(self, value):
        self._log.debug(f'Setting token to {value}')
        self.__token = value
        self.token_info = Token(session=self)
        self._log.debug(f'token_info updated with {self.token_info}')

    @property
    def _log(self):
        return logging.getLogger(f'GuildWars2API.{self.__class__.__name__}')

    @property
    def _headers(self):
        if self.token:
            return {'Authorization': f'Bearer {self.token}'}
        return {}

    def make_request(self, url, params=None, data=None, headers=None,
                     auth=False):
        if auth and not self.token:
            self._log.error(f'auth specified, but token = {repr(self.token)}')
            raise AuthorizationRequiredError(
                'This request requires authentication that is not present. '
                'Please set a token using load_token() or setting token to a '
                'string value.'
            )
        api_url = f'{GW2APISession._base_url}/{url}'
        if params:
            api_url = f'{api_url}?{urlencode(params)}'
        api_data = data
        api_headers = self._headers
        if headers:
            api_headers.update(headers)
        self._log.debug(f'Requesting:\n'
                        f'      URL: {api_url}\n'
                        f'     Data: {api_data}\n'
                        f'  Headers: {api_headers}')
        req = Request(api_url, api_data, headers=api_headers)
        try:
            resp = urlopen(req)
            return loads(resp.read())
        except (HTTPError, URLError, JSONDecodeError) as e:
            logging.exception(e)
            raise APIError from e

    def load_token(self, file_path):
        self._log.debug(f'Loading token from {file_path}')
        with open(file_path, mode='r') as f:
            self.token = f.read()


class GW2API(object):
    _endpoint_url = ''

    def __init__(self, session=None):
        self._log.debug(
            f'{self.__class__.__name__} init with session {session}'
        )
        self._session = session \
            if isinstance(session, GW2APISession) \
            else GW2APISession()

    @property
    def _log(self):
        return logging.getLogger(f'GuildWars2API.{self.__class__.__name__}')


class GW2Thing(GW2API):
    def __init__(self, id=None, session=None, auth=False):
        super(GW2Thing, self).__init__(session=session)
        if id is None:
            params = {}
        else:
            params = {'id': id}
        info = self._session.make_request(self._endpoint_url, params=params,
                                          auth=auth)
        self._log.debug(f'Response:\n{pformat(info)}')
        self._update_obj(info)

    def __repr__(self):
        item_name = self.__class__.__name__
        item_desc = getattr(self, "name", getattr(self, "id", None))
        return f'<{item_name} "{item_desc}">'

    def _update_obj(self, info):
        for k, v in info.items():
            self._log.debug(f'Setting {self.__class__.__name__}.{k} to {v}')
            self.__dict__[k] = v

    @property
    def details(self):
        return f'{repr(self)}\n' + \
               '\n'.join([f'{k:>20}: {v}'
                          for k, v in self.__dict__.items()
                          if not callable(v) and not k.startswith('_')])


class GW2List(GW2API):
    _thing_type = GW2Thing

    def __init__(self, session=None, auth=False):
        super(GW2List, self).__init__(session=session)
        self._things = None
        self.count = 0
        self._auth = auth

    def __iter__(self):
        if self._things is None:
            self.refresh()
        return iter(self._things)

    def __repr__(self):
        items = '(Empty)' if self._things is None \
            else f'{len(self._things)} items'
        return f'<{self.__class__.__name__} {items}>'

    def refresh(self):
        self._log.info('Refreshing {}'.format(self))
        things = self._session.make_request(self._endpoint_url, auth=self._auth)
        self._things = []
        for thing in things:
            self._log.debug(f'Processing: {thing}')
            if thing and thing.get('id'):
                thing_obj = self._thing_type(
                    thing.get('id'), session=self._session)
                thing_obj._update_obj(thing)
                self._things.append(thing_obj)
            else:
                self._log.warning(f'Skipping: {thing}')
        self.count = len(self._things)
        self._log.info(f'Found {self.count} items')


class GW2Enum(GW2API):
    _thing_type = GW2Thing

    def __init__(self, session=None):
        super(GW2Enum, self).__init__(session=session)

    def __repr__(self):
        return f'<{self.__class__.__name__} of {self._thing_type.__name__}>'

    def get(self, id):
        if id is None:
            id = 'all'
        if any(isinstance(id, t) for t in (list, tuple)):
            return [
                self._thing_type(g)
                for g in self._session.make_request(
                    self._endpoint_url, {'ids': id}
                )
            ]
        else:
            return self._thing_type(
                self._session.make_request(self._endpoint_url, {'id': id})
            )


class Token(GW2Thing):
    _endpoint_url = 'v2/tokeninfo'

    def __repr__(self):
        return f'<{self.__class__.__name__} "{self.name}" with scopes ' \
               f'{", ".join(self.permissions)}>'

    def __str__(self):
        return f'"{self.name}" with scopes {", ".join(self.permissions)}'


class Account(GW2Thing):
    _endpoint_url = 'v2/account'

    def __init__(self, session=None):
        super(Account, self).__init__(session=session, auth=True)
        self.world = World(self.world, session=session)
        self.guilds = [Guild(g, session=session) for g in self.guilds]
        self.bank = Bank(session=session)
        self.characters = Characters(session=session)
        self._log.debug(f'Account initialized with {self.__dict__}')


class Character(GW2Thing):
    _endpoint_url = 'v2/characters'


class Characters(GW2List):
    _endpoint_url = 'v2/characters'
    _thing_type = Character

    def refresh(self):
        self._log.info('Refreshing {}'.format(self))
        things = self._session.make_request(self._endpoint_url, auth=self._auth)
        self._things = []
        for thing in things:
            self._log.debug(f'Processing: {thing}')
            thing_obj = self._thing_type(thing, session=self._session)
            self._things.append(thing_obj)
        self.count = len(self._things)
        self._log.info(f'Found {self.count} items')


class Guild(GW2Thing):
    _endpoint_url = 'v2/guild'

    def __init__(self, id, session=None):
        self._endpoint_url = Guild._endpoint_url + f'/{id}'
        super(Guild, self).__init__(session=session)


class Guilds(GW2Enum):
    _endpoint_url = 'v2/guild'
    _thing_type = Guild


class World(GW2Thing):
    _endpoint_url = 'v2/worlds'


class Worlds(GW2Enum):
    _endpoint_url = 'v2/worlds'
    _thing_type = World


class Item(GW2Thing):
    _endpoint_url = 'v2/items'


class Items(GW2Enum):
    _endpoint_url = 'v2/items'
    _thing_type = Item


class BankItem(Item):
    def __repr__(self):
        item_name = self.__class__.__name__
        item_desc = getattr(self, 'name', getattr(self, 'id', None))
        item_count = getattr(self, 'count', 'Unknown')
        return f'<{item_name} "{item_desc}" x {item_count}>'


class Bank(GW2List):
    _endpoint_url = 'v2/account/bank'
    _thing_type = BankItem


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s - %(name)s - %(message)s'
    )

    session = GW2APISession()
    session.load_token('token.txt')

    me = Account(session=session)
    print(me.details)

    # me.bank.refresh()
    # print('Bank items:\n')
    # for i in me.bank:
    #     print(i.details)
    #     print()

    me.characters.refresh()
    print('Characters:\n')
    for c in me.characters:
        print(c.details)
        print()

import logging
import time

from json import JSONDecodeError, loads
from multiprocessing.pool import ThreadPool
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
    """
    Exception to be raised if an API requires authorization and no token is
    available.
    """
    pass


class TokenMissingScope(Exception):
    """
    Exception to be raised if an API requires a scope that the current token
    does not have.
    """
    pass


class APIError(Exception):
    """
    Error to be raised if we encounter communication errors.
    """
    pass


class GW2APISession(object):
    """Session object. Keeps the token."""
    _base_url = 'https://api.guildwars2.com'

    def __init__(self):
        """
        Prepares a session for use.
        """
        self.__token = None
        self.token_info = None
        self._log.debug(f'Initialized {self}')

    def __repr__(self):
        state = 'Unauthenticated' \
            if self.token_info is None \
            else f'Authenticated with {str(self.token_info)}'
        return f'<{self.__class__.__name__} {state}>'

    @property
    def token(self):
        """Get the token value."""
        return self.__token

    @token.setter
    def token(self, value):
        """
        Sets the token value, and makes an API call to get token info, storing
        it in self.token_info.
        """
        self._log.debug(f'Setting token to {value}')
        self.__token = value
        self.token_info = Token(session=self)
        self._log.debug(f'token_info updated with {self.token_info}')

    @property
    def _log(self):
        """Logger"""
        return logging.getLogger(f'GuildWars2API.{self.__class__.__name__}')

    @property
    def _headers(self):
        """Get a dictionary of headers."""
        if self.token:
            return {'Authorization': f'Bearer {self.token}'}
        return {}

    def make_request(self, url, params=None, data=None, headers=None):
        """
        Make an API request.

        Args:
            url (str): Endpoint URL to call.
            params (dict, optional): Parameters to add to the URL.
            data (dict, optional): Data to send in the request payload.
            headers (dict, optional): Headers to send on the request. Starts
                with the self._headers, and updates that dictionary with these
                values.

        Returns (dict):
            Dictionary converted from the JSON data returned.

        Raises:
            AuthorizationRequiredError: If the endpoint required
                authorization, but none is provided.
            APIError: If we have trouble contacting the endpoint, or the data
                that comes back can't be converted properly.
        """
        api_url = f'{GW2APISession._base_url}/{url}'
        if params:
            params = urlencode(params, safe=',')
            api_url = f'{api_url}?{params}'
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
        """
        Load a token from a file.

        Args:
            file_path (str): Path to the file containing the token.
        """
        self._log.debug(f'Loading token from {file_path}')
        with open(file_path, mode='r') as f:
            self.token = f.read()


class GW2API(object):
    """Parent class for an API endpoint. Other classes derive off of this."""
    _endpoint_url = ''
    _required_scopes = []

    def __init__(self, session=None):
        """
        Prepare a GW2API object for use.

        Args:
            session (GW2APISession, optional): A session object. Defaults to
                None, which results in a new session.

        Raises:
            TokenMissingScope: If the object requires a scope and the session
                does not have a token with the appropriate scopes.
        """
        self._log.debug(
            f'{self.__class__.__name__} init with session {session}'
        )
        self._session = session \
            if isinstance(session, GW2APISession) \
            else GW2APISession()
        if self._required_scopes:
            scopes = getattr(self._session.token_info, 'permissions', [])
            if not all(s in scopes for s in scopes):
                err = f'{self.__class__.__name__} is missing required ' \
                      f'scopes.\n' \
                      f'Need: {self._required_scopes}\n' \
                      f'Have: {scopes}'
                self._log.error(err)
                raise TokenMissingScope(err)

    @property
    def _log(self):
        """Logger"""
        return logging.getLogger(f'GuildWars2API.{self.__class__.__name__}')


class GW2Thing(GW2API):
    """
    A class representing a single item (an Item, Recipe, Character,
    etc). Properties are dynamically set based on the API return value.

    Ensure the _endpoint_url class variable is set specific for the item.
    """
    def __init__(self, id=None, session=None):
        """
        Prepares a GW2Thing for use.

        Args:
            id (str, optional): An ID that the item corresponds to.
            session (GW2APISession, optiona): Session to make requests from.
                Defaults to None, which results in a new session. Session is
                passed to child objects.
            authentication? Defaults to False.
        """
        super(GW2Thing, self).__init__(session=session)
        if isinstance(id, dict):
            self._update_obj(id)
        else:
            self.id = id
            self.refresh()
        self._log.info(f'Initialized {self}')

    def __repr__(self):
        """repr() output"""
        item_name = self.__class__.__name__
        item_desc = getattr(self, "name", getattr(self, "id", None))
        return f'<{item_name} "{item_desc}">'

    def _update_obj(self, info):
        """
        Add the properties from a dictionary to the object, logging each one.

        Args:
            info (dict): Dictionary with the new values.
        """
        self._log.debug(f'Updating {self} with: {info}')
        for k, v in info.items():
            self._log.debug(f'Setting {self.__class__.__name__}.{k} to {v}')
            self.__dict__[k] = v
        self._log.debug(f'Updated {self}')

    @property
    def details(self):
        """Get a nice string representation of all properties on the object."""
        return f'{repr(self)}\n' + \
               '\n'.join([f'{k:>20}: {v}'
                          for k, v in self.__dict__.items()
                          if not callable(v) and not k.startswith('_')])

    def refresh(self):
        params = {} if getattr(self, 'id', None) is None else {'id': self.id}
        info = self._session.make_request(self._endpoint_url, params=params)
        self._log.debug(f'Response:\n{pformat(info)}')
        self._update_obj(info)


class GW2List(GW2API):
    """
    A class representing a list of things, either passed to the class,
    or gleaned from an API. The class will be initialized with with the list
    of ids or make a single request for the items.

    Calling refresh() will cause the list to go make threaded API calls for
    the individual items.

    Ensure that the _endpoint_url and _thing_type are set for subclasses.
    _thing_type should be a GW2Thing subclass.
    """
    _thing_type = GW2Thing
    _enum_type = None

    def __init__(self, session=None, ids=None):
        """
        Prepares a GW2List for initial use.

        Args:
            session (GW2APISession, optional): Session to use to make requests.
            ids (list or tuple, optional): List or tuple of Ids. Defaults to
                None (which makes an API call).
        """
        super(GW2List, self).__init__(session=session)
        self._things = None
        self.count = 0
        self._ids = ids if ids else self._session.make_request(
            self._endpoint_url)
        self._log.info(f'Initialized {self}')

    def __iter__(self):
        """
        Iterate over the items. Causes a refresh if it hasn't been previously.
        """
        if self._things is None:
            self.refresh()
        return iter(self._things)

    def __repr__(self):
        """repr() output"""
        item_name = self._thing_type.__name__
        items = f'{len(self._things)} {item_name} items' \
            if self._things is not None \
            else f'{len(self._ids)} {item_name} items' \
            if self._ids is not None \
            else f'?? {item_name} items'
        return f'<{self.__class__.__name__} {items}>'

    def refresh(self):
        """
        Go get all of the items and wrap them into their item classes. This
        method uses a ThreadPool to make all of the API calls in parallel,
        which uses a number of threads equal to the number of CPU cores.
        """
        self._log.info(f'Refreshing {self}')
        self._log.debug(f'ID list to query:\n{pformat(self._ids)}')
        timer = time.time()
        if self._enum_type and all(isinstance(i, dict) for i in self._ids):
            got_things = self._enum_type(session=self._session)\
                .get([i.get('id') for i in self._ids])
            for got_thing, orig_thing in zip(got_things, self._ids):
                if got_thing.id == orig_thing.get('id'):
                    got_thing._update_obj(orig_thing)
            self._things = got_things
        elif self._enum_type:
            self._things = self._enum_type.get(self._ids)
        else:
            with ThreadPool(1) as pool:
                got_things = pool.map(
                    self.get_thing,
                    [(self._session, self._thing_type, t)
                     for t in self._ids]
                )
            self._things = [t for t in got_things if t is not None]
        self.count = len(self._things)
        req_time = time.time() - timer
        self._log.info(f'Found {self.count} items in {req_time:4.2f}s')

    @staticmethod
    def get_thing(args):
        """
        Static method called by the ThreadPool to make API calls and get
        objects.

        Args:
            args (tuple): A 3 element tuple containing the session,
                thing_type, and thing to get.

        Returns (GWThing):
            A GW2Thing object of thing_type type that represents the item.
        """
        MODULE_LOG.debug(f'get_thing with: {args}')
        session, thing_type, thing = args
        if isinstance(thing, dict) and thing.get('id'):
            thing_obj = thing_type(thing.get('id'), session=session)
            thing_obj._update_obj(thing)
        elif isinstance(thing, str):
            thing_obj = thing_type(thing, session=session)
        else:
            return None
        return thing_obj


class GW2Enum(GW2API):
    """
    A class representing an Enumeration of types. Usually, these types allow
    searching for specifics items based on criteria.

    Ensure _thing_type is set in subclasses.
    """
    _thing_type = GW2Thing

    def __init__(self, session=None):
        """
        Prepare a GW2Enum for use.

        Args:
            session (GW2APISession, optional): Session to use to make calls.
                Defaults to None, which is replaced with a new session.
        """
        super(GW2Enum, self).__init__(session=session)
        self._log.info(f'Initialized {self}')

    def __repr__(self):
        """repr() output."""
        return f'<{self.__class__.__name__} of {self._thing_type.__name__}>'

    def get(self, id=None):
        """
        Get a specified item by id.

        Args:
            id (str or list, optional): ID to call for. Defaults to None,
                which is replaced with 'all'.

        Returns (GW2Thing):
            A GW2Thing of the type in self._thing_type with the object.
        """
        if id is None:
            id = 'all'
        if any(isinstance(id, t) for t in (list, tuple)):
            for i in range(0, len(id), 3):
                ids = ','.join([str(a) for a in id[i:i+20]])
                return [
                    self._thing_type(g, session=self._session)
                    for g in self._session.make_request(
                        self._endpoint_url, params={'ids': ids}
                    )
                ]
        else:
            return self._thing_type(
                self._session.make_request(self._endpoint_url, {'id': id}),
                session=self._session,
            )


class Token(GW2Thing):
    """Token object"""
    _endpoint_url = 'v2/tokeninfo'

    def __repr__(self):
        item_name = getattr(self, 'name', 'Unknown')
        item_perms = getattr(self, 'permissions', [])
        return f'<{self.__class__.__name__} "{item_name}" with scopes ' \
               f'{", ".join(item_perms)}>'

    def __str__(self):
        item_name = getattr(self, 'name', 'Unknown')
        item_perms = getattr(self, 'permissions', [])
        return f'"{item_name}" with scopes {", ".join(item_perms)}'


class Account(GW2Thing):
    """Account object"""
    _endpoint_url = 'v2/account'
    _required_scopes = ['account']

    def __init__(self, session=None):
        super(Account, self).__init__(session=session)
        self.world = World(self.world, session=session)
        self.guilds = MyGuilds(ids=self.guilds, session=session)
        self.bank = Bank(session=session)
        self.characters = MyCharacters(session=session)
        self.achievements = MyAchievements(session=session)
        self._log.debug(f'Account initialized with {self.__dict__}')


class Character(GW2Thing):
    """Character object"""
    _endpoint_url = 'v2/characters'
    _required_scopes = ['characters']

    def __init__(self, id, session=None):
        super(Character, self).__init__(id, session=session)
        self.guild = Guild(self.guild, session=session)
        self.recipes = MyRecipes(ids=self.recipes, session=session)
        self.equipment = MyEquipment(ids=self.equipment, session=session)


class MyCharacters(GW2List):
    """Collection of Characters for Account"""
    _endpoint_url = 'v2/characters'
    _thing_type = Character
    _required_scopes = ['characters']


class Guild(GW2Thing):
    """Guild object"""
    _endpoint_url = 'v2/guild'

    def __init__(self, id, session=None):
        self._endpoint_url = Guild._endpoint_url + f'/{id}'
        super(Guild, self).__init__(session=session)


class Guilds(GW2Enum):
    """Collection of Guilds"""
    _endpoint_url = 'v2/guild'
    _thing_type = Guild


class MyGuilds(GW2List):
    """Collection of Guilds for Account"""
    _thing_type = Guild


class World(GW2Thing):
    """World object"""
    _endpoint_url = 'v2/worlds'


class Worlds(GW2Enum):
    """Collection of Worlds"""
    _endpoint_url = 'v2/worlds'
    _thing_type = World


class Item(GW2Thing):
    """Item object"""
    _endpoint_url = 'v2/items'


class Items(GW2Enum):
    """Collection of items"""
    _endpoint_url = 'v2/items'
    _thing_type = Item


class Recipe(GW2Thing):
    """Recipe object"""
    _endpoint_url = 'v2/recipes'


class Recipes(GW2Enum):
    """Collection of Recipes"""
    _endpoint_url = 'v2/recipes'
    _thing_type = Recipe


class MyRecipes(GW2List):
    """Collection of Recipes on a Character"""
    _thing_type = Recipe


class EquippedItem(Item):
    """An Equipped Item object"""
    def __repr__(self):
        item_name = self.__class__.__name__
        item_desc = getattr(self, 'name', getattr(self, 'id', 'Unknown'))
        item_slot = getattr(self, 'slot', 'Unknown')
        return f'<{item_name} "{item_desc}" in slot {item_slot}>'


class MyEquipment(GW2List):
    """Collection of Equipped Item on a Character"""
    _thing_type = EquippedItem


class BankItem(Item):
    """An Item in the bank."""
    def __repr__(self):
        item_name = self.__class__.__name__
        item_desc = getattr(self, 'name', getattr(self, 'id', None))
        item_count = getattr(self, 'count', 'Unknown')
        return f'<{item_name} "{item_desc}" x {item_count}>'


class Bank(GW2List):
    """Collection of Bank Items on an Account"""
    _endpoint_url = 'v2/account/bank'
    _thing_type = BankItem
    _required_scopes = ['inventories']


class Achievement(GW2Thing):
    _endpoint_url = 'v2/achievements'


class Achievements(GW2Enum):
    _endpoint_url = 'v2/achievements'
    _thing_type = Achievement


class MyAchievements(GW2List):
    _endpoint_url = 'v2/account/achievements'
    _thing_type = Achievement
    _enum_type = Achievements
    _required_scopes = ['progression']


if __name__ == '__main__':
    import sys
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
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

    me.achievements.refresh()
    print('Achievements:\n')
    for a in me.achievements:
        print(a.details)
        print()

    # me.characters.refresh()
    # print('Characters:\n')
    # for c in me.characters:
    #     print(c.details)
    #     for e in c.equipment:
    #         print(e)
    #     print()

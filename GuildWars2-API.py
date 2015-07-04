import json
import urllib
import urllib2

# Active endpoints:
# /v2/account
# /v2/account/bank
# /v2/account/materials
# /v2/build
# /v2/characters
# /v2/colors
# /v2/commerce/exchange
# /v2/commerce/exchange/coins
# /v2/commerce/exchange/gems
# /v2/commerce/listings
# /v2/commerce/prices
# /v2/commerce/transactions
# /v2/continents
# /v2/files
# /v2/floors
# /v2/items
# /v2/maps
# /v2/materials
# /v2/quaggans
# /v2/recipes
# /v2/recipes/search
# /v2/skins
# /v2/tokeninfo
# /v2/worlds


class GuildWars2_Broker(object):
    """
    Provides methods and properties for making API reqeusts, tracking API
    tokens, and maintaining a connection.
    """

    _base_url = 'https://api.guildwars2.com'

    def __init__(self):
        self._token = None

    def make_request(self, endpoint_url, params=None, payload=None,
                     headers=None,
                     auth=False):
        """
        Make a request to the Guild Wars 2 API.

        PARAMETERS
        endpoint_url    String of the URL endpoint.
        params          Dictionary of URL parameters to send.
        payload         String of the payload to be sent. Defaults to a null
                            string.
        headers         Dict of the headers to be sent. Appended to the standard
                            headers. Defaults to an empty dict.
        auth            Boolean of whether this request should be authenticated.
                            Defaults to False.

        RETURN VALUES
        Python formatted JSON (dict)
        """
        # Build the url, including params if they are given.
        api_url = '{0}{1}'.format(self._base_url, endpoint_url)
        if params:
            api_url = '{0}?{1}'.format(api_url, urllib.urlencode(params))
        # Build the payload.
        api_payload = payload
        # Get the standard headers and amend any provided headers.
        api_headers = self.std_headers(auth)
        if headers:
            api_headers.update(headers)
        # Build the request.
        req = urllib2.Request(api_url, data=api_payload, headers=api_headers)
        # Call the request and get response.
        try:
            resp = urllib2.urlopen(req)
        except (urllib2.HTTPError, urllib2.URLError) as e:
            raise APIError('There was an error with the request.\n'
                           'URL: {0}\n'
                           'Error: {1}'.format(api_url, e))
        # Return the results.
        return json.loads(resp.read())

    def token_from_file(self, file_path):
        """
        Load a token from a text file.

        PARAMETERS
        file_path       String of the path to the file.

        RETURN VALUES
        The string Token value.
        """
        token = open(file_path, mode='r').read()
        self._token = token
        return token

    def token_from_string(self, token):
        """
        Load a token from a string.

        PARAMETERS
        token           String of the token to be set.

        RETURN VALUES
        The string Token value.
        """
        self._token = token
        return token

    def std_headers(self, auth=False):
        """
        Gets the standard headers.

        PARAMETERS
        auth            Boolean of whether the headers are for an                                           authenticated request or not. Defaults to                                       False.

        RETURN VALUES
        A dict of header values.
        """
        if auth:
            return {'Authorization': 'Bearer {0}'.format(self._token)}
        else:
            return {}


class AuthorizationRequried(Exception):
    """
    Error returned when authorization is required.
    """
    pass


class APIError(Exception):
    """
    Error returned for general failures.
    """
    pass


class Account(object):
    """
    Provides access to account metadata.
    """
    _endpoint_url = '/v2/account'

    def __init__(self):
        pass


class Character(object):
    _endpoint_url = '/v2/characters'

    def __init__(self):
        pass


class TokenInfo(object):
    _endpoint_url = '/v2/tokeninfo'

    def __init__(self):
        pass


class Items(object):
    _endpoint_url = '/v2/items'

    def __init__(self):
        pass


class Recipes(object):
    _endpoint_url = '/v2/recipes'

    def __init__(self):
        pass


class Skins(object):
    _endpoint_url = '/v2/skins'

    def __init__(self):
        pass


class Continents(object):
    _endpoint_url = '/v2/continents'

    def __init__(self):
        pass


class Maps(object):
    _endpoint_url = '/v2/maps'

    def __init__(self):
        pass


class Build(object):
    _endpoint_url = '/v2/build'

    def __init__(self):
        pass


class Colors(object):
    """
    Access the colors of Guild Wars 2.

    PUBLIC METHODS
    get()       Gets a specified color or colors.

    PUBLIC PROPERTIES
    _endpoint_url   URL of the API endpoint.
    _broker         Broker object used for requests.
    ids             List of color IDs.
    """
    _endpoint_url = '/v2/colors'

    def __init__(self, broker=None):
        """
        Prepares a Colors object for use.

        PARAMETERS
        broker      Broker to use for requests. If not specified, creates one.
        """
        self._broker = GuildWars2_Broker()
        if broker:
            self._broker = broker
        self.ids = self._broker.make_request(self._endpoint_url)

    def get(self, color_id):
        """
        Get a specific color.

        PARAMETERS
        color_id        Int, List of Ints, or Tuple of Ints IDs to get.

        RETURN VALUE
        None if any of the specified IDs are not in self.ids. Returns a Color
        object or list of Color objects otherwise. For more information, see:
        http://wiki.guildwars2.com/wiki/API:2/colors
        """
        if type(color_id) in (list, tuple):
            if not all(item in self.ids for item in color_id):
                return None
            else:
                color_id = [str(cid) for cid in color_id]
                return [Color(item)
                        for item in self._broker.make_request(
                        self._endpoint_url, {'ids': ','.join(color_id)})]
        elif type(color_id) is int:
            if color_id not in self.ids:
                return None
            else:
                return Color(
                    self._broker.make_request(self._endpoint_url,
                                              {'id': color_id}))
        else:
            return None


class Color(object):
    """
    A specific color.

    PUBLIC PROPERTIES
    id          Integer ID of the color.
    name        String of the color name.
    rgb         List of ints of the color values.
    cloth       Dict of cloth properties.
    leather     Dict of leather properties.
    metal       Dict of metal properties.
    """

    def __init__(self, color_dict):
        """
        Creates a color object for use.

        PARAMETERS
        color_dict      Dict of color values.
        """
        self.id = color_dict['id']
        self.name = color_dict['name']
        self.rgb = color_dict['base_rgb']
        self.cloth = color_dict['cloth']
        self.leather = color_dict['leather']
        self.metal = color_dict['metal']

    def __repr__(self):
        """
        String representation: "Color {name} ({id})"
        """
        return 'Color {0} ({1})'.format(self.name, self.id)


class Assets(object):
    _endpoint_url = '/v2/files'

    def __init__(self):
        pass


class Quaggans(object):
    """
    Allows access to the quaggan objects.

    PUBLIC METHODS
    get()       Gets information on a specific quaggan.

    PUBLIC PROPERTIES
    _broker     Broker object uses for communication.
    ids         Dictionary of all Quaggans.
    """
    _endpoint_url = '/v2/quaggans'

    def __init__(self, broker=None):
        """
        Prepares an object for use.

        PARAMETERS
        broker      Broker to use for requests. If not specified, creates one.
        """
        self._broker = GuildWars2_Broker()
        if broker:
            self._broker = broker
        self.ids = self._broker.make_request(self._endpoint_url)

    def get(self, quaggan_name):
        """
        Gets a specific quaggan from the list.

        PARAMETERS
        quaggan_name        String, list of strings, or list of tuples of the
                                quaggans to get.

        RETURN VALUES
        None if any of the specified quaggans are not in self.ids. Returns a
        dictionary of information otherwise. See the following URL for details:
        http://wiki.guildwars2.com/wiki/API:2/quaggans
        """
        if type(quaggan_name) in (list, tuple):
            if all(item in self.ids for item in quaggan_name):
                return self._broker.make_request(
                    self._endpoint_url, params={'ids': ','.join(quaggan_name)})
            else:
                return None
        else:
            if quaggan_name not in self.ids:
                return None
            else:
                return self._broker.make_request(
                    '{0}/{1}'.format(self._endpoint_url, quaggan_name))


class Worlds(object):
    _endpoint_url = '/v2/worlds'

    def __init__(self):
        pass


if __name__ == '__main__':
    import pprint

    # Test Quaggans
    quaggans = Quaggans()
    pprint.pprint(quaggans.ids)
    pprint.pprint(quaggans.get('404'))
    pprint.pprint(quaggans.get(['404', 'rain', 'scifi']))

    # Test Colors
    colors = Colors()
    pprint.pprint(colors.ids)
    pprint.pprint(colors.get(10))
    pprint.pprint(colors.get([10, 11, 12, 13]))

import requests, sys, urllib.parse, os.path, time, json
from Logger import Logger
from threading import RLock, Thread

NUMBER_OF_THREADS = 4
FF_API_DIRECTORY_URL = "https://raw.githubusercontent.com/freifunk/directory.api.freifunk.net/master/directory.json"
TIMEOUT = 5

class UrlSet(object):
    def __init__(self, urls = None):
        self.lock = RLock()
        self.urls = set()
        if urls is not None:
            self.urls |= (urls)

    def isEmpty(self):
        self.lock.acquire()
        result = (self.urls == True)
        self.lock.release()
        return result

    def getAllUrls(self):
        self.lock.acquire()
        result = set()
        result |= self.urls
        self.lock.release()
        return result

    def addUrl(self, url):
        self.lock.acquire()
        self.urls.add(url)
        self.lock.release()

    def addUrls(self, urls):
        self.lock.acquire()
        self.urls |= urls
        self.lock.release()

    # Returns the next URL or None if the list is empty
    def getUrl(self):
        self.lock.acquire()
        if not self.urls:
            url = None
        else:
            url = self.urls.pop()
        self.lock.release()
        return url

class NodeDict(object):

    def __init__(self):
        self.nodes = {}
        self.lock = RLock()

    def addNodes(self, nodes):
        self.lock.acquire()
        self.nodes.update(nodes)
        self.lock.release()

    def getNodes(self):
        self.lock.acquire()
        result = {}
        result.update(self.nodes)
        self.lock.release()
        return result

def get_ff_api_urls(logger):

    response = requests.get(FF_API_DIRECTORY_URL , allow_redirects=True, timeout=TIMEOUT)
    if response.status_code == requests.codes.ok:
        data = response.json()
        ff_api_urls = set(data.values())
        logger.log("API directory OK")
        return UrlSet(ff_api_urls)
    else:
        logger.log("API directory " + FF_API_DIRECTORY_URL  + " response status code: " + str(response.status_code))
        logger.log("Aborting")
        sys.exit()


def get_map_urls(ff_api_urls, logger, ff_urls, nodelist_urls):
    api_url = ff_api_urls.getUrl()
    while api_url is not None:
        try:
            response = requests.get(api_url, allow_redirects=True, timeout=TIMEOUT)
            if response.status_code == requests.codes.ok:
                data = response.json()
                nodeMaps = data.get("nodeMaps", None)
                if nodeMaps is not None:
                    found_ffmap_urls = set()
                    found_nodelist = False
                    for nodeMapsEntry in nodeMaps:
                        type = nodeMapsEntry.get("technicalType", None)
                        if type is not None:
                            if type == "ffmap":
                                url = nodeMapsEntry.get("url", None)
                                if url is not None:
                                    found_ffmap_urls.add(url)
                            elif type == "nodelist":
                                url = nodeMapsEntry.get("url", None)
                                if url is not None:
                                    found_nodelist = True
                                    nodelist_urls.addUrl(url)
                                logger.log("API " + api_url + ": nodelist url " + url + " added")
                    # Use ffmap_urls only if no nodelist entry was found.
                    if not found_nodelist:
                        ff_urls.addUrls(found_ffmap_urls)
                        logger.log("API " + api_url + ": ffmap url(s) " + str(found_ffmap_urls) + " added")
                else:
                    logger.log("API " + api_url + " has no 'nodeMaps' entry")
            else:
                logger.log("API " + api_url + " request status code: " + str(response.status_code))
        # Reading json failed
        except ValueError as e:
            logger.log("API " + api_url + " " + str(e))
        # Downloading the json file failed
        except requests.exceptions.RequestException as e:
            logger.log("API " + api_url + " " + str(e))

        api_url = ff_api_urls.getUrl()


def get_nodes_json_url_from_map_url(url):
    # Try to get the location of nodes.json from the url to the ffmap
    parse = urllib.parse.urlparse(url)
    if len(parse.path) == 0:
        new_url = url + "/nodes.json"
    else:
        dirname = os.path.dirname(parse.path)
        if dirname[-1:] == '/':
            dirname += "nodes.json"
        else:
            dirname += "/nodes.json"
        new_url = urllib.parse.urlunparse((parse[0], parse[1], dirname, "", "", ""))
    return new_url

def get_nodes_json_urls(ffmaps_urls):
    # Get url of nodes.json from map url
    ffmaps_urls_set = ffmaps_urls.getAllUrls()
    nodes_json_urls = set()

    for url in ffmaps_urls_set:
        new_url = get_nodes_json_url_from_map_url(url)
        nodes_json_urls.add(new_url)

    return UrlSet(nodes_json_urls)

def get_nodes_from_nodes_json_urls(nodes_json_urls, nodes_out, logger):
    url = nodes_json_urls.getUrl()
    while url is not None:
        try:
            response = requests.get(url, allow_redirects=True, timeout=TIMEOUT)
            if response.status_code == requests.codes.ok:
                data = response.json()
                if data is not None:
                    nodes_json = data.get("nodes", None)
                    if type(nodes_json) == type(dict()):
                        nodes = get_nodes_from_nodes_json(nodes_json)
                        logger.log(url + ": " + str(len(nodes)) + " node(s) found")
                        nodes_out.addNodes(nodes)

                    elif type(nodes_json) == type(list()):
                        nodes = get_nodes_from_nodes_json2(nodes_json)
                        logger.log(url + ": " + str(len(nodes)) + " node(s) found")
                        nodes_out.addNodes(nodes)
                    else:
                        logger.log(url + ": could not parse json")
                else:
                    logger.log(url + " response is none")
            else:
                logger.log(url + " response status code: " +  str(response.status_code))
        # Downloading from URL failed
        except requests.exceptions.RequestException as e:
            logger.log(url + " " + str(e))
        # Reading the json failed.
        except ValueError as e:
            logger.log(url + " ValueError " + str(e))

        url = nodes_json_urls.getUrl()


def get_nodes_from_nodes_json(nodes):
    nodes_out = {}
    for key, value in nodes.items():
        try:
            node_out = {'online': value['flags']['online'], 'lat': value['nodeinfo']['location']['latitude'],
                        'lon': value['nodeinfo']['location']['longitude'], 'name': value['nodeinfo']['hostname']}
            nodes_out[key] = node_out
        # caused by missing key in json
        except KeyError as e:
            pass
    return nodes_out

def get_nodes_from_nodes_json2(nodes):
    nodes_out = {}
    for n in nodes:
        try:
            node_out = {'online': n['flags']['online'], 'lat': n['geo'][0], 'lon': n['geo'][1], 'name': n['name']}
            nodes_out[n['id']] = node_out
        # caused by missing key in json
        except KeyError as e:
            pass
        # caused by 'geo':none
        except TypeError as e:
            pass
    return nodes_out


def get_nodes_from_nodelist_urls(nodelist_urls, nodes_out, logger):
    url = nodelist_urls.getUrl()
    while url is not None:
        try:
            response = requests.get(url, allow_redirects=True, timeout=TIMEOUT)
            if response.status_code == requests.codes.ok:
                data = response.json()
                nodes = get_nodes_from_nodelist_json(data)
                logger.log(url + ": " + str(len(nodes)) + " node(s) found")
                nodes_out.addNodes(nodes)
            else:
                logger.log(url + " response status code: " +  str(response.status_code))
        # Downloading from URL failed
        except requests.exceptions.RequestException as e:
            logger.log(url + " " + str(e))
        # Reading the json failed.
        except ValueError as e:
            logger.log(url + " ValueError " + str(e))

        url = nodelist_urls.getUrl()

def get_nodes_from_nodelist_json(json):
    nodes_out = {}
    nodes = json['nodes']
    for n in nodes:
        try:
            node_out = {'online': n['status']['online'], 'lat': n['position']['lat'], 'lon': n['position']['long'],
                        'name': n['name']}
            nodes_out[n['id']] = node_out
        except KeyError:
            pass
        except TypeError:
            pass
    return nodes_out


def write_json_to_file(data):
    with open('nodes.json', 'w') as outfile:
        json.dump(data, outfile)

def main():
    start_time = time.perf_counter()

    # Setup logger
    log_to_console = '-p' in sys.argv
    logger = Logger('log.txt', log_to_console)
    # Get urls of the community api files from the api directory
    ff_api_urls = get_ff_api_urls(logger)

    # Get the urls to the nodelist and nodes_json files
    ff_urls = UrlSet()
    nodelist_urls = UrlSet()

    threads = []
    for i in range(0, NUMBER_OF_THREADS):
        thread = Thread(target=get_map_urls, args=(ff_api_urls, logger, ff_urls, nodelist_urls))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    nodes_json_urls = get_nodes_json_urls(ff_urls)

    # Get the nodes from the nodes_json_urls
    nodes = NodeDict()

    threads = []
    for i in range(0, NUMBER_OF_THREADS):
        thread = Thread(target=get_nodes_from_nodes_json_urls, args=(nodes_json_urls, nodes, logger))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # Get the nodes from the nodelist_urls
    threads = []
    for i in range(0, NUMBER_OF_THREADS):
        thread = Thread(target=get_nodes_from_nodelist_urls, args=(nodelist_urls, nodes, logger))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # Write found nodes in a json file.
    data = dict()
    data['timestamp'] = int(time.time())
    nodes_out = nodes.getNodes()
    logger.log(str(len(nodes_out)) + " nodes found.")
    data['nodes'] = nodes_out
    write_json_to_file(data)

    end_time = time.perf_counter()
    duration = end_time - start_time
    logger.log('Elapsed time: ' + str(duration))

if __name__ == '__main__':
    main()

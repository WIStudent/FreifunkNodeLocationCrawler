import requests, urllib.parse, os.path, json, time, sys


def get_ff_api_urls():
    url = "https://raw.githubusercontent.com/freifunk/directory.api.freifunk.net/master/directory.json"
    response = requests.get(url, allow_redirects=True)
    if response.status_code == requests.codes.ok:
        data = response.json()
        ff_api_urls = list(data.values())
        return ff_api_urls
    else:
        print("API directory " + url + " response status code: " + str(response.status_code))
        print("Aborting")
        sys.exit()

def get_map_urls(ff_api_urls):
    ff_urls = set()
    nodelist_urls = set()
    for api_url in ff_api_urls:
        try:
            response = requests.get(api_url, allow_redirects=True)
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
                                    nodelist_urls.add(url)
                    # Use ffmap_urls only if no nodelist entry was found.
                    if not found_nodelist:
                        ff_urls |= found_ffmap_urls
            else:
                print("API " + api_url + " request status code: " + str(response.status_code))
        # Reading json failed
        except ValueError as e:
            print("API " + api_url + " " + str(e))
        # Downloading the json file failed
        except requests.exceptions.RequestException as e:
            print("API " + api_url + " " + str(e))

    return {'ffmap': ff_urls, 'nodelist': nodelist_urls}


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


def get_nodes_from_ffmaps_urls(ffmaps_urls):
    # Get url of nodes.json from map url
    nodes_json_urls = set()
    for url in ffmaps_urls:
        new_url = get_nodes_json_url_from_map_url(url)
        nodes_json_urls.add(new_url)

    nodes_out = {}
    for n in nodes_json_urls:
        try:
            response = requests.get(n, allow_redirects=True)
            if response.status_code == requests.codes.ok:
                data = response.json()
                if data is not None:
                    nodes_json = data.get("nodes", None)
                    if type(nodes_json) == type(dict()):
                        nodes = get_nodes_from_nodes_json(nodes_json)
                        nodes_out.update(nodes)
                    elif type(nodes_json) == type(list()):
                        nodes = get_nodes_from_nodes_json2(nodes_json)
                        nodes_out.update(nodes)
                    else:
                        print("couldnt parse " + n)
                else:
                    print(n + " response is none")
            else:
                print(n + " response status code: " +  str(response.status_code))
        # Downloading from URL failed
        except requests.exceptions.RequestException as e:
            print(n + " " + str(e))
        # Reading the json failed.
        except ValueError as e:
            print(n + " ValueError " + str(e))

    print("Number of Nodes: " + str(len(nodes_out)))
    return nodes_out


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


def get_nodes_from_nodelist_urls(nodelist_urls):
    nodes_out = {}
    for n in nodelist_urls:
        try:
            response = requests.get(n, allow_redirects=True)
            if response.status_code == requests.codes.ok:
                data = response.json()
                nodes = get_nodes_from_nodelist_json(data)
                nodes_out.update(nodes)
            else:
                print(n + " response status code: " +  str(response.status_code))
        # Downloading from URL failed
        except requests.exceptions.RequestException as e:
            print(n + " " + str(e))
        # Reading the json failed.
        except ValueError as e:
            print(n + " ValueError " + str(e))

    print("Number of Nodes: " + str(len(nodes_out)))
    return nodes_out


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


# Get urls of the community api files from the api directory
ff_api_urls = get_ff_api_urls()
# Get urls to the maps and nodelists from the community api files
maps_urls = get_map_urls(ff_api_urls)
# Get nodes from ffmaps
nodes = get_nodes_from_ffmaps_urls(maps_urls['ffmap'])
# Get nodes from nodelists
nodes.update(get_nodes_from_nodelist_urls(maps_urls['nodelist']))
# Write found nodes in a json file.
data = dict()
data['timestamp'] = int(time.time())
data['nodes'] = nodes
write_json_to_file(data)

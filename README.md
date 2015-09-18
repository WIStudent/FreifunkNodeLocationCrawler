# FreifunkNodeLocationCrawler
&copy; 2015 [Tobias Trumm](mailto:tobiastrumm@uni-muenster.de) licensed under MIT licence

## Info
The script uses the [Freifunk API](https://github.com/freifunk/directory.api.freifunk.net) to collect location information about Freifunk nodes and writes it into a single json file. It searches for [ffmap](https://github.com/ffnord/ffmap-backend/tree/master) and [nodelist](https://github.com/ffansbach/nodelist) urls in the API files of the different Freifunk communities and tries to extract the information about the nodes from these files.

## Dependencies
- Python 3
- [requests](http://www.python-requests.org/)
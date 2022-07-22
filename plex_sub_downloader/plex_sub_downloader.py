import os
import argparse
import json
import jsonschema
import sys
from flask import Flask, request, Response
from .logger import Logger
import logging
from .PlexWebhookEvent import PlexWebhookEvent
from .PlexSubDownloader import PlexSubDownloader

log = Logger.getInstance().getLogger()
psd = PlexSubDownloader() 
APP = Flask(__name__)


@APP.route('/webhook', methods=['POST'])
def respond():
    """
    Handle POST request sent from Plex server
    """
    data = json.loads(request.form.get('payload'))
    log.debug(data)
    log.debug("\n\n\n")

    event = PlexWebhookEvent(data)
    psd.handleWebhookEvent(event)
    return Response(status=200)


def main():

    usage = ("{FILE} "
             "--config <config_file.json> "
             "--debug "
             "<command> (one of: configtest, start-webhook)"
             ).format(FILE=__file__)

    description = 'Download subtitles for recently added Plex media'
    parser = argparse.ArgumentParser(usage=usage, description=description)
    parser.add_argument("-c", "--config", help="Config File", default="config.json")
    parser.add_argument("-d", "--debug", help="Set log level to Debug", action='store_true', required=False)
    parser.add_argument("command", 
    nargs="+",
    choices=["configtest", "start-webhook"],
    help="Command to perform"
    )

    parser.set_defaults(debug=False)

    args = parser.parse_args()

    if args.debug:
        Logger.getInstance().enableDebug()
    else:
        #this is a hack to stop Flask from logging every single request to the console
        logging.getLogger('werkzeug').disabled = True

    config = loadConfig(args.config)
    log.debug("cmdline arguments:")
    log.debug(args)
    log.debug("Config params:")
    log.debug(config)

    Logger.getInstance().setLevel(level=config.get('log_level',logging.INFO))

    if "configtest" in args.command:
        log.info(f'Testing config file \'{args.config}\'')
        schema = loadConfig(os.path.join(os.path.abspath(os.path.dirname(__file__)), "config.schema.json"))
        jsonschema.validate(instance=config, schema=schema)
        log.info('config file is valid.')
        return
    
    

    if psd.configure(config) == False:
        log.error("An error occurred during configuration.")
        return
    
    if "start-webhook" in args.command:
        log.info("plex-sub-downloader starting up")
        runFlask(config)
        log.info("plex-sub-downloader shutting down")

    
    


def loadConfig(filepath):

    with open(filepath, 'r') as fp:
        config = json.load(fp)
        return config  


def runFlask(config):

    APP.run(host=config.get('webhook_host', None), port=config.get('webhook_port', None))


if __name__ == '__main__':
    main()

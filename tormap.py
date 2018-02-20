#!/usr/bin/env python
# encoding: utf-8

'''
 quick and dirty hack Moritz Bartl moritz@torservers.net
 13.12.2010

 Changes by George Kargiotakis kargig[at]void[dot]gr
 01.11.2012

 Change script to use onionnoo json by George Kargiotakis kargig[at]void[dot]gr
 28.11.2017

 Switch to OpenStreetMap by George Kargiotakis kargig[at]void[dot]gr
 01.12.2017

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU Lesser General Public License (LGPL)
 as published by the Free Software Foundation, either version 3 of the
 License, or any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU Lesser General Public License for more details.

 https://www.gnu.org/licenses/
'''

#Variables
FAST = 5000000
MAPDIR='maps/'
HTMLDIR = '/var/www/'
KMLDIR = HTMLDIR+MAPDIR
TMPDIR= '/tmp/tormap/'

import os
import re
import cgi
from string import Template
import random
import json
import sys

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def parsejson():
  with open(TMPDIR+'relays.json', 'r') as relay_file:
    types = json.load(relay_file)
    for relay in types['relays']:
      # use only the ones that are found running in consensus
      if relay['running'] == True:
        # add jitter for geolocation
        try:
            relay['latitude'] = relay['latitude'] + random.random()/(5*10)
            relay['longitude'] = relay['longitude'] + random.random()/(5*10)
        except:
            relay['latitude'] = random.random()/(5*10)
            relay['longitude'] = random.random()/(5*10)
        for address in relay['or_addresses']:
          if address.startswith('['):
            try:
                result = re.search('(\[.*\]):(.*)', address)
                ipv6  = result.group(1)
                oport = result.group(2)
                relay['ipv6'] = ipv6
                relay['orport6'] = oport
                relay['address6'] = address
            except:
                pass
          else:
            oport = address.split(':')[-1]
            ip = address.split(':')[0]
            relay['ipv4'] = ip
            relay['orport4'] = oport
        fingerprint = relay['fingerprint']
        if 'BadExit' in relay['flags']:
            badRelays[fingerprint] = relay
        elif 'Authority' in relay['flags']:
            authRelays[fingerprint] = relay
        elif 'Exit' in relay['flags']:
          if relay.has_key('observed_bandwidth') and relay['observed_bandwidth']>FAST:
            exitFastRelays[fingerprint] = relay
          else:
            exitRelays[fingerprint] = relay
        elif 'Stable' in relay['flags']:
          if relay.has_key('observed_bandwidth') and relay['observed_bandwidth']>FAST:
            stableFastRelays[fingerprint] = relay
          else:
            stableRelays[fingerprint] = relay
        else:
            otherRelays[fingerprint] = relay
    print 'Bad:', len(badRelays)
    print 'Exit:', len(exitRelays)
    print 'Fast exit:', len(exitFastRelays)
    print 'Non-exit stable:', len(stableRelays)
    print 'Fast non-exit stable:', len(stableFastRelays)
    print 'Authority:', len(authRelays)
    print 'Other:', len(otherRelays)
    inConsensus = len(authRelays)+len(badRelays)+len(exitRelays)+len(stableRelays)+len(otherRelays)
    print '[ in consensus:', inConsensus, ']'
    notInConsensus = len(types['relays'])-len(badRelays)-len(exitRelays)-len(stableRelays)-len(otherRelays)
    print '[ cached descriptors not in consensus:', notInConsensus, ']'

def generateFolder(name, styleUrl, relays):
        placemarkTemplate = Template ('<Placemark>\n\
            <name>$nickname</name>\n\
            <description>\n\
            <![CDATA[\n\
            <p><strong>IPv4</strong>: <a href="https://centralops.net/co/DomainDossier.aspx?dom_whois=1&net_whois=1&dom_dns=1&addr=$ipv4">$ipv4:$orport4</a></p>\n\
            <p><strong>IPv6</strong>: <a href="https://centralops.net/co/DomainDossier.aspx?dom_whois=1&net_whois=1&dom_dns=1&addr=$ipv6">$address6</a></p>\n\
            <p><strong>Directory Address</strong>: $dir_address</p>\n\
            <p><strong>Bandwidth</strong>: $observed_bandwidth</p>\n\
            <p><strong>Flags</strong>: $flatflags</p>\n\
            <p><strong>Up since</strong>: $last_restarted</p>\n\
            <p><strong>Contact</strong>: $contact</p>\n\
            <p><strong>IPv4 Policy</strong>: $exit_policy_summary</p>\n\
            <p><strong>IPv6 Policy</strong>: $exit_policy_v6_summary</p>\n\
            <p><strong>Fingerprint</strong>: <a href="https://metrics.torproject.org/rs.html#details/$fingerprint">$prettyFingerprint</a></p>\n\
            <p><strong>Country</strong>: $country_name</p>\n\
            <p><strong>Platform</strong>: $platform</p>\n\
            <p><strong>Recommended Version</strong>: $recommended_version</p>\n\
            ]]>\n\
            </description>\n\
            <styleUrl>$styleUrl</styleUrl>\n\
            <Point>\n\
                <coordinates>$longitude,$latitude</coordinates>\n\
            </Point>\n\
            </Placemark>\n\
            ')

        group = '<Folder>\n<name>%s</name>\n' % name
        for fingerprint,relay in relays.items():
            # for displaying: pretty fingerprint in blocks of four, uppercase
            relay['prettyFingerprint'] = " ".join(filter(None, re.split('(\w{4})', fingerprint.upper())))
            relay['styleUrl'] = styleUrl
            relay['observed_bandwidth'] = sizeof_fmt(relay['observed_bandwidth'])
            relay['flatflags'] = ",".join(relay['flags'])
            if 'ipv6' not in relay:
                relay['ipv6'] = ''
                relay['orport6'] = ''
                relay['address6'] = ''
            if 'exit_policy_v6_summary' not in relay:
                relay['exit_policy_v6_summary'] = ''
            else:
                relay['exit_policy_v6_summary'] = json.dumps(relay['exit_policy_v6_summary']).replace("{","").replace("}", "").replace('"','')
            if 'contact' not in relay:
                relay['contact'] = 'None'
            else:
                relay['contact'] = cgi.escape(relay['contact'])
            if 'dir_address' not in relay:
                relay['dir_address'] = ''
            relay['exit_policy_summary'] = json.dumps(relay['exit_policy_summary']).replace("{","").replace("}", "").replace('"','')
            placemark = placemarkTemplate.safe_substitute(relay)
            group = group + placemark
        group = group + "\n</Folder>"
        return group

def genkml():
        # generate KML
        kmlBody = ()

        parts = icon_dict.keys()
        for part in parts:
            kmlBody = ''
            if part == 'auth':
                kmlBody = kmlBody + generateFolder("%s Authority nodes" % len(authRelays), "#auth", authRelays)
            elif part == 'bad':
                kmlBody = kmlBody + generateFolder("%s Bad" % len(badRelays), "#bad", badRelays)
            elif part == 'exitFast':
                kmlBody = kmlBody + generateFolder("%s Fast Exits (>= 5MB/s)" % len(exitFastRelays), "#exitFast", exitFastRelays)
            elif part == 'exit':
                kmlBody = kmlBody + generateFolder("%s Exits" % len(exitRelays), "#exit", exitRelays)
            elif part == 'stableFast':
                kmlBody = kmlBody + generateFolder("%s Fast stable nodes (>= 5MB/s)" % len(stableFastRelays), "#stableFast", stableFastRelays)
            elif part == 'stable':
                kmlBody = kmlBody + generateFolder("%s Stable nodes" % len(stableRelays), "#stable", stableRelays)
            elif part == 'other':
                kmlBody = kmlBody + generateFolder("%s Other" % len(otherRelays), "#other", otherRelays)

            if not os.path.exists(KMLDIR):
                os.makedirs(KMLDIR)
            kml = open(KMLDIR + 'tormap_' + part + '.kml', 'w')

            styletag=(
                '   <Style id="'+ part + '">\n'
                '        <IconStyle>\n'
                '            <Icon>\n'
                '                <href>' + icon_dict[part] + '</href>\n'
                '            </Icon>\n'
                '            <hotSpot x="0.1" y="0" xunits="fraction" yunits="fraction" />\n'
                '        </IconStyle>\n'
                '    </Style>\n'
             )

            kmlHeader_top = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<kml xmlns="https://www.opengis.net/kml/2.2" xmlns:gx="https://www.google.com/kml/ext/2.2" xmlns:kml="https://www.opengis.net/kml/2.2" xmlns:atom="https://www.w3.org/2005/Atom">\n'
                '<Document>\n'
                '    <name>Tor relays</name>\n'
            )

            kmlFooter = ('</Document>\n'
                             '</kml>\n')

            kml.write(kmlHeader_top)
            kml.write(styletag)
            kml.write(kmlBody)
            kml.write(kmlFooter)
            kml.close()

def genhtml():
        htmlHeader_top = (
            '<html>\n'
            '  <head>\n'
            '    <meta name="viewport" content="initial-scale=1.0, user-scalable=no">\n'
            '    <meta charset="utf-8">\n'
            '    <title>World City Map of Tor Nodes</title>\n'
            '    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.2.0/dist/leaflet.css" />\n'
            '    <script src="https://unpkg.com/leaflet@1.2.0/dist/leaflet.js"></script>\n'
            '    <script type="text/javascript" src="leaflet-color-markers/js/leaflet-color-markers.js"></script>\n'
            '    <script type="text/javascript" src="osm.js"></script>\n'
            '    <link href="default.css" rel="stylesheet">\n'
            '    <script src="leaflet-plugins/layer/vector/KML.js"></script>\n'
            '  </head>\n'
            '  <body onload="initialize()">\n'
            '    <p align="left">\n'
            '    <a href="https://www.torproject.org"><img alt="Tor Logo" src="tor-logo.jpg" /></a>\n'
        )

        htmlFooter = (
            '    <br /></p>\n'
            '    <div id="map_canvas" style="width: 100%; height: 86%; float: left"></div>\n'
            '    <br />Read more at <a href="https://github.com/kargig/tormap">https://github.com/kargig/tormap</a> | Click on the category links in the header to download the appropriate KML files\n'
            '  </body>\n'
            '</html>\n'
        )

        htmlBody = ()
        htmlBody = ''
        #we need a certain order inside the html
        parts = ['other','stable','stableFast','exit','exitFast','auth','bad']
        for part in parts:
            if part == 'auth':
                htmlBody += (
                        '    <img alt="Authority" style="img" src="' + icon_dict[part] + '" />\n'
                        '    <input onclick="toggleAuthority();" type="checkbox" value="Authority" checked/><a href="'+MAPDIR+'tormap_'+part+'.kml">Authority</a> ('
                        + str(len(authRelays)) + ')   \n'
                        )
            elif part == 'bad':
                htmlBody += (
                        '    <img alt="Bad" style="img" src="'+ icon_dict[part] + '" />\n'
                        '    <input onclick="toggleBad();" type="checkbox" value="Bad" checked/><a href="'+MAPDIR+'tormap_'+part+'.kml">Bad</a> ('
                        + str(len(badRelays)) + ')   \n'
                        )
            elif part == 'exitFast':
                htmlBody += (
                        '    <img alt="FastExit" style="img" src="' + icon_dict[part] + '" />\n'
                        '    <input onclick="toggleFastExit();" type="checkbox" value="Fast Exits" checked/><a href="'+MAPDIR+'tormap_'+part+'.kml">Fast Exit</a> (>5Mb/s) ('
                        + str(len(exitFastRelays)) + ')   \n'
                        )
            elif part == 'exit':
                htmlBody += (
                        '    <img alt="Exit" style="img" src="' + icon_dict[part] + '" />\n'
                        '    <input onclick="toggleExit();" type="checkbox" value="Exit" checked/><a href="'+MAPDIR+'tormap_'+part+'.kml">Exit</a> ('
                        + str(len(exitRelays)) + ')   \n'
                        )
            elif part == 'stableFast':
                htmlBody += (
                        '    <img alt="FastStable" style="img" src="' + icon_dict[part] + '" />\n'
                        '    <input onclick="toggleFastStable();" type="checkbox" value="Fast Stable"/><a href="'+MAPDIR+'tormap_'+part+'.kml">Fast Stable</a> (>5Mb/s) ('
                        + str(len(stableFastRelays)) + ')   \n'
                        )
            elif part == 'stable':
                htmlBody += (
                        '    <img alt="Stable" style="img" src="' + icon_dict[part] + '" />\n'
                        '    <input onclick="toggleStable();" type="checkbox" value="Stable" /><a href="'+MAPDIR+'tormap_'+part+'.kml">Stable</a> ('
                        + str(len(stableRelays)) + ')   \n'
                        )
            elif part == 'other':
                htmlBody += (
                        '    <img alt="Other" style="img" src="' + icon_dict[part] + '" />\n'
                        '    <input onclick="toggleOther();" type="checkbox" value="Other" /><a href="'+MAPDIR+'tormap_'+part+'.kml">Other</a> ('
                        + str(len(otherRelays)) + ')   \n'
                        )

        if not os.path.exists(HTMLDIR):
            os.makedirs(HTMLDIR)
        html = open(HTMLDIR + 'osm.html', 'w')
        html.write(htmlHeader_top)
        html.write(htmlBody)
        html.write(htmlFooter)
        html.close()

def main(argv=None):
    parsejson()
    genkml()
    genhtml()

if __name__ == "__main__":
    icon_dict = {
        'auth':'/leaflet-color-markers/img/marker-icon-blue.png',
        'bad':'/images/danger.png',
        'exitFast':'/leaflet-color-markers/img/marker-icon-red.png',
        'exit':'/leaflet-color-markers/img/marker-icon-green.png',
        'stableFast':'/leaflet-color-markers/img/marker-icon-violet.png',
        'stable':'/leaflet-color-markers/img/marker-icon-yellow.png',
        'other':'/leaflet-color-markers/img/marker-icon-grey.png',
    }
    badRelays = dict() # Bad in flags, eg. BadExit, BadDirectory
    exitFastRelays = dict() # Exit flag, >= FAST
    exitRelays = dict() # Exit flag, slower than FAST
    stableFastRelays = dict() # Stable flag, but not Exit
    stableRelays = dict() # Stable flag, but not Exit
    authRelays = dict() # Authority flag
    otherRelays = dict() # non Stable, non Exit
    sys.exit(main())

#!/bin/bash	
rm -rf /opt/sofa
rm -f /usr/local/bin/sofastat.py
rm -f /usr/local/bin/sofa
mkdir -p /opt/sofa/bin
mkdir -p /opt/sofa/sofaboard
mkdir -p /opt/sofa/plugin
cp -i sofa /opt/sofa/bin
cp -i sofastat.py /opt/sofa/bin
cp sofaboard/app.js /opt/sofa/sofaboard
cp sofaboard/index.html /opt/sofa/sofaboard
cp sofaboard/paracord.html /opt/sofa/sofaboard
ln -is /opt/sofa/bin/sofa /usr/local/bin/sofa
ln -is /opt/sofa/bin/sofastat.py /usr/local/bin/sofastat.py


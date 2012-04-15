#!/bin/bash

localedir=`dirname $0`
echo Generating messages.pot ...
pygettext.py -o $localedir/messages.pot ultrablog/*.py

# zh_CN
if ! [ -f $localedir/zh_CN.po ]; then
    echo Generating zh_CN.po ...
    msginit -l zh_CN -i $localedir/messages.pot -o $localedir/zh_CN.po
else
    echo Merging zh_CN.po ...
    msgmerge -U $localedir/zh_CN.po $localedir/messages.pot
    gvim -f $localedir/zh_CN.po
fi
echo Generating ultrablog.mo ...
msgfmt.py -o $localedir/zh_CN/LC_MESSAGES/ultrablog.mo $localedir/zh_CN.po

# en_US
if ! [ -f $localedir/en_US.po ]; then
    echo Generating en_US.po ...
    msginit -l en_US -i $localedir/messages.pot -o $localedir/en_US.po
else
    echo Merging en_US.po ...
    msgmerge -U $localedir/en_US.po $localedir/messages.pot
    gvim -f $localedir/en_US.po
fi
echo Generating ultrablog.mo ...
msgfmt.py -o $localedir/en_US/LC_MESSAGES/ultrablog.mo $localedir/en_US.po

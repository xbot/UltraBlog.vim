#!/bin/bash

basedir=`dirname $0`
cd $basedir
apack UltraBlog.zip doc/UltraBlog.txt plugin/UltraBlog.vim plugin/ultrablog/*.py plugin/locale/{en_US,zh_CN}
cd -

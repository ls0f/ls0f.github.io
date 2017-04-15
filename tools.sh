#!/bin/bash

ser(){
	echo http://localhost:8000
	(
	cd output
	python -m pelican.server
	)
}

article(){
	title=$1
	name=content/`echo "$title"|tr " " "-"`.md
	now=`date "+%Y-%m-%d %H:%M"`
	cat > $name <<EOF
Title: $title
Date: $now


EOF
/Applications/Byword.app/Contents/MacOS/Byword $name &
}


sync(){
	rsync -avz output/ do:web/blog/
}

if [[ $1 == "ser" ]]; then
    ser
elif [[ $1 == "article" ]]; then
	article "$2"
elif [[ $1 == "sync" ]]; then
	sync
fi

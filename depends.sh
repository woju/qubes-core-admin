#!/bin/bash -e
# vim: set ts=4 sw=4 sts=4 et :

##
## Install python depends from .spec file
## (for development purposes)
##

##
## The Qubes OS Project, http://www.qubes-os.org
## Copyright (C) 2014 Jason Mehring <nrgaway@gmail.com>
##  
## License: GNU General Public License
##

#path="$(readlink -m $0)"
#dir="${path%/*}"
dir="$PWD"

# Spec files to parse
DEFAULT_SPEC="${dir}/rpm_spec/*.spec"
SPEC=${1-"${DEFAULT_SPEC}"}
FILTER="python"

HR_MAX_LENGTH=128
HR_CHAR='-'

# Colors
reset=$(    tput sgr0   || tput me      )
red=$(      tput setaf 1|| tput AF 1    )
blue=$(     tput setaf 4|| tput AF 4    )

function Len() {
    local len="${1}"

    re='^[0-9]+$'
    if ! [[ $len =~ $re ]] ; then
        len=${#len}
    fi    

    echo $len
}

function Hr() {
    local len=${1-80}
    local char="${2-"${HR_CHAR}"}"

    len=$(Len $len)
    while [ ${len} -gt 0 ]; do
        printf "${char}"
        len=$[$len-1]
    done
    echo
}

function Decolorize() {
    local string="${1}"

    echo "$(sed -e "s/\x1b\[[0-9;]\{1,5\}m//g" <<< "$string")"
}

function HrTitle() {
    local title="${1}"
    local title_decolorized="$(Decolorize "${title}")"
    local len="${2-${#title_decolorized}}"
    local char="${3-"${HR_CHAR}"}"
    len=$(Len $len)

    printf "${title} "
    Hr $[$len-${#title_decolorized}-1] "$char"
    printf "${reset}"
}

function InstallDepends() {
    local depends="${1}"
    local title="${2-"${blue}DEPENDS - SPEC FILE"}"
    local color="${3-"${blue}"}"

    local char='-'
    local len=80

    HrTitle "${color}${char} ${title}" ${len} "${color}${char}"
    echo ${depends} | fold -w $len -s
    Hr ${len} "${color}${char}"
    echo
    sudo yum install ${depends}
}

echo

depends="$(rpmspec -q --requires ${SPEC} | uniq | grep "${FILTER}")"
InstallDepends "${depends}" 

if [ -f "${dir}/depends.missing" ]; then
    depends="$(cat "${dir}/depends.missing")"
    InstallDepends "${depends}" "DEPENDS - MISSING FROM SPEC FILE" "${red}"
fi


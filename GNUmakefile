# Time-stamp: <11-Jul-2012 10:29:15 PDT by rich.pixley@palm.com>

# Copyright (c) 2010 - 2012 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

default: all

unamem := $(shell uname -m)

venv := rcmp-dev
pythonbin := ${venv}/bin

python := ${pythonbin}/python
activate := . ${pythonbin}/activate
pydoctor := ${venv}/bin/pydoctor
epydoc := ${venv}/bin/epydoc

arpy_egg := ${venv}/lib/python2.6/site-packages/arpy-0.2.0-py2.6.egg
cpiofile_egg := ${venv}/lib/python2.6/site-packages/cpiofile-0.003-py2.6.egg
elffile_egg := ${venv}/lib/python2.6/site-packages/elffile-0.005-py2.6.egg
nose_egg := ${venv}/lib/python2.6/site-packages/nose-1.0.0-py2.6.egg

all: ${nose_egg} ${elffile_egg} ${cpiofile_egg} #${arpy_egg}

define eggmake
$(1): ${$(1)_egg}
${$(1)_egg}: ${python}
	${activate} && easy_install -U $(1)
endef

$(eval $(call eggmake,arpy))
$(eval $(call eggmake,cpiofile))
$(eval $(call eggmake,elffile))
$(eval $(call eggmake,nose))

stamp-maverick: stamp-apt
	sudo apt-get install --yes python-nose
	touch $@-new && mv $@-new $@

.PHONY: ve
ve: ${python}
${python}: stamp-virtualenv
	virtualenv --no-site-packages rcmp-dev

stamp-virtualenv: stamp-apt
	sudo easy_install -U virtualenv
	touch $@-new && mv $@-new $@

# firefox is only needed for reading the doc
DEBIANS_NOT := \
	apt-file \
	build-essential \
	bzr \
	debhelper \
	firefox \
	libapache2-mod-wsgi \
	libspread1 \
	libspread1-dev \
	python-dev \
	python-epydoc \
	python-nevow \
	python-twisted \
	python-yaml \
	yaml-mode \
	libyaml-dev \
	spread \

DEBIANS := \
	python-setuptools \
	python-sphinx \
	python-virtualenv \

stamp-apt:
	sudo apt-get install --yes ${DEBIANS}
	touch $@-new && mv $@-new $@

clean:
	rm -rf ${venv} stamp-virtualenv stamp-apt pydoctor build \
		dist rcmp.egg-info stamp-lucid *.pyc apidocs

check: all
	${activate} && time python setup.py nosetests

doc: ${pydoctor}
	${activate} && pydoctor --add-module=rcmp.py \
		--add-module=test_rcmp.py \
		--add-module=test_spread.py \
		&& firefox apidocs/index.html

setuppy.%: ${python}
	${activate} && python setup.py $*

# Time-stamp: <24-Sep-2013 10:31:53 PDT by rich@noir.com>

# Copyright © 2013 K Richard Pixley
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

all: build
unames := $(shell uname -s)

packagename := rcmp

venvsuffix := 

pyver := 2.7
vpython := python${pyver}

ifeq (${unames},Darwin)
virtualenv := /Library/Frameworks/Python.framework/Versions/${pyver}/bin/virtualenv
else
ifeq (${unames},Linux)
virtualenv := virtualenv -p ${vpython}
else
$(error Unrecognized system)
endif
endif

venvbase := ${packagename}-dev
venv := ${venvbase}-${pyver}
pythonbin := ${venv}/bin
python := ${pythonbin}/python

activate := . ${pythonbin}/activate
setuppy := ${activate} && python setup.py
pypitest := -r https://testpypi.python.org/pypi

pydoctor := ${venv}/bin/pydoctor

.PHONY: ve
ve: ${python}
${python}:
	${virtualenv} --no-site-packages ${venv}
	find ${venv} -name distribute\* -o -name setuptools\* \
		| xargs rm -rf
	${activate} && python distribute_setup.py

clean:
	rm -rf ${venvbase}* .stamp-virtualenv .stamp-apt build \
		dist ${packagename}.egg-info *.pyc apidocs *.egg *~

# doc: ${pydoctor}
# 	${activate} && pydoctor --add-module=rcmp.py \
# 		--add-module=test_rcmp.py \
# 		--add-module=test_spread.py \
# 		&& firefox apidocs/index.html

setuppy.%: ${python}
	${activate} && python setup.py $*

.PHONY: build
build: rcmp.egg-info/SOURCES.txt

rcmp.egg-info/SOURCES.txt: rcmp/__init__.py setup.py ${python}
	${setuppy} build

.PHONY: check
check: ${python} develop
	${setuppy} nosetests

sdist_format := bztar

.PHONY: sdist
sdist: ${python}
	${setuppy} sdist --formats=${sdist_format}

.PHONY: bdist
bdist: ${python}
	${setuppy} bdist

.PHONY: develop
develop: ${venv}/lib/${vpython}/site-packages/${packagename}.egg-link

${venv}/lib/${vpython}/site-packages/${packagename}.egg-link: setup.py ${python} rcmp/__init__.py
	${setuppy} --version 
	#${setuppy} lint
	${setuppy} develop

.PHONY: bdist_upload
bdist_upload: ${python} 
	${setuppy} bdist_egg upload ${pypitest}

.PHONY: sdist_upload
sdist_upload: ${python}
	${setuppy} sdist --formats=${sdist_format} upload ${pypitest}

.PHONY: register
register: ${python}
	${setuppy} $@ ${pypitest}

long.html: long.rst
	${setuppy} build
	docutils-*-py${pyver}.egg/EGG-INFO/scripts/rst2html.py $< > $@-new && mv $@-new $@

long.rst: ; ${setuppy} --long-description > $@-new && mv $@-new $@


.PHONY: bdist_egg
bdist_egg: ${python}
	${setuppy} $@

doctrigger = docs/build/html/index.html

.PHONY: docs
docs: ${doctrigger}
${doctrigger}: ${python} docs/source/index.rst ${packagename}/__init__.py
	${setuppy} build_sphinx

.PHONY: lint
lint: ${python}
	${setuppy} $@

.PHONY: install
install: ${python}
	${setuppy} $@

.PHONY: build_sphinx
build_sphinx: ${python}
	${setuppy} $@

.PHONY: nosetests
nosetests: ${python}
	${setuppy} $@

.PHONY: test
test: ${python}
	${setuppy} $@

.PHONY: docs_upload upload_docs
upload_docs docs_upload: ${doctrigger}
	${setuppy} upload_docs ${pypitest}

supported_versions := \
	2.7 \

bigcheck: ${supported_versions:%=bigcheck-%}
bigcheck-%:; $(MAKE) pyver=$* check

bigupload: register sdist_upload ${supported_versions:%=bigupload-%} docs_upload
bigupload-%:; $(MAKE) pyver=$* bdist_upload

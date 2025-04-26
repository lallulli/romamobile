cd /opt
7z x pyjs.7z
cd pyjs
python2 bootstrap.py
python2 run_bootstrap_first_then_setup.py install
cd /build
/opt/pyjs/bin/pyjsbuild --no-compile-inplace --no-keep-lib-files main.py

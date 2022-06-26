function testIab() {
	 var ref = window.open('http://www.google.com', '_blank', 'location=yes');
	 ref.addEventListener('loadstart', function(event) { alert('start: ' + event.url); });
	 ref.addEventListener('loadstop', function(event) { alert('stop: ' + event.url); });
	 ref.addEventListener('exit', function(event) { alert(event.type); });
}

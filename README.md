# Requirement Service - Python

## Tasks

- [ ] Projekt strukturieren / aufbauen
- [ ] Tests schreiben
- [ ] File Reader modularisieren (ABC o.ä. erstellen, um das Interface zu definieren und JSONL klasse extrahieren)
- [ ] Installations Doku schreiben
- [ ] Excel Wrapper implementieren

### Projekt strukturieren

- [ ] pyproject.toml fertig konfigurieren, damit die Projektdaten und Requirenments korrekt abgebildet sind.
  - [ ] Python 3.10 oder neuer. (3.11) ist auch ok.
  - [ ] requirements [sanic, pydantic] ggf. Click für CLI interface. 
  - [ ] dev-requirements (mal schauen, wie wir pyproject.toml und bootstrap.py gleichzeitig nutzen können)
- [ ] projekt soll paketierbar sein als Wheel mit FLIT
- [ ] project soll editable installierbar sein
- [ ] Entrypoint sollte vorhanden sein.

### Tests schreiben

- [ ] Robot Framework Systemtests für jeden Call
- [ ] optinal unit tests Pytest?

### File Reader modularisieren

- [ ] Sanic configurierbar machen
  - [ ] https soll funktionieren
  - [ ] basedir über CLI setzen
  - [ ] wichtigsten Sanic configs setzen können (serve_ip, port, https?, Authentication, etc.)
- [ ] File Reader sollten configurierbar sein und dynamisch geladen werden.
  - [ ] Nötige Config für die Reader sollten aus der Config file gelesen werden.




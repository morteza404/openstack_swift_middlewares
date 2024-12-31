#### how to run test?

```bash
python3 -m venv venv

source venv/bin/activate

pip install swift==2.27.0 pytest coverage

pytest -v --cov=. --cov-report=html:cover --cov-report=term
```

# service-scheduler 
 A django app for creating and fine-tuning "fair" schedules using 
 * [PuLP](https://coin-or.github.io/pulp/) optimization 
 * Postgresql
 * pdfkit

## Install
```bash
pip install -r requirements.txt
```

## Seed your data
add data to `core/fixtures`

_read scripts for now to understand data format for now_

```bash
./manage.py seed_data
```


## Models
![models](models.png?raw=true)

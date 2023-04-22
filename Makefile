.PHONY: run deploy

run:
	railway run python main.py

deploy:
	railway up

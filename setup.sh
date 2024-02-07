if [ ! -f ./app/data/data.db ]
then
    touch ./app/data/data.db
fi

pip install --upgrade pip

pip install --no-cache-dir --upgrade -r requirements.txt

python -m spacy download en_core_web_sm

python -m nltk.downloader popular
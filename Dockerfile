FROM jupyter/scipy-notebook:latest

WORKDIR /home/jovyan/work

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m spacy download es_core_news_md \
    && python -m nltk.downloader -d /home/jovyan/nltk_data punkt punkt_tab stopwords wordnet omw-1.4

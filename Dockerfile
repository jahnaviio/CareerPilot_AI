FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /app
COPY requirements.txt requirements-ml.txt ./
# Build with --build-arg ML=1 to include Sentence Transformers (large image).
ARG ML=0
RUN if [ "$ML" = "1" ]; then pip install --no-cache-dir -r requirements-ml.txt; else pip install --no-cache-dir -r requirements.txt; fi
COPY . .
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request,os;urllib.request.urlopen('http://localhost:%s/_stcore/health'%os.environ.get('PORT','8501'))"
CMD ["sh", "-c", "alembic upgrade head && streamlit run app.py --server.port ${PORT:-8501} --server.address 0.0.0.0"]

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN python manage.py collectstatic --noinput

RUN groupadd -g 1000 appuser && useradd -u 1000 -g 1000 -m -d /home/appuser appuser && chown -R appuser:appuser /app
USER appuser

COPY --chown=appuser:appuser entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "picky_picker_web.wsgi:application", "--bind", "0.0.0.0:80", "--workers", "3", "--timeout", "60"]

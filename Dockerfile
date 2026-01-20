# 공식 Python 3.12 slim 이미지를 사용합니다.
FROM python:3.12-slim

# 작업 디렉토리를 /app으로 설정합니다.
WORKDIR /app

# requirements.txt를 복사하고 라이브러리를 설치합니다.
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 나머지 모든 애플리케이션 코드를 복사합니다.
COPY . .

# 내부 포트 8080 노출
EXPOSE 8080

# (★★수정★★) $PORT 변수 대신 8080 숫자를 직접 입력 (확실한 실행 보장)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]

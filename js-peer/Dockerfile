FROM node:18-alpine

WORKDIR /app

COPY package.json .

RUN npm install

ARG port
ENV env_port $port
EXPOSE $port

CMD ["npm", "run", "dev"]
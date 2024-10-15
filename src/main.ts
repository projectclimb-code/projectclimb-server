import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  console.log('Starting app on port: \t', process.env.PORT);
  console.log('Connecting to DB: \t', process.env.DATABASE_URL);
  console.log('Files locatiom: \t', process.env.FILE_STORAGE);

  const app = await NestFactory.create(AppModule);
  await app.listen(process.env.PORT);
}
bootstrap();

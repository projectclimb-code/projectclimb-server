import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { MulterModule } from '@nestjs/platform-express';
import { MongooseModule } from '@nestjs/mongoose';

@Module({
  imports: [
    MongooseModule.forRoot(process.env.DATABASE_URL),
    MulterModule.register({
      dest: process.env.FILE_STORAGE,
    }),
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}

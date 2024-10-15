import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { MulterModule } from '@nestjs/platform-express';
import { MongooseModule } from '@nestjs/mongoose';
import { RoutesModule } from './modules/routes/routes.module';
import { ConfigModule } from '@nestjs/config';

@Module({
  imports: [
    ConfigModule.forRoot(),
    MongooseModule.forRoot(process.env.DATABASE_URL),
    RoutesModule,
    MulterModule.register({
      dest: '../upload',
    }),
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}

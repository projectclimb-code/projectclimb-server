import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { MongooseModule } from '@nestjs/mongoose';
import { RoutesModule } from './modules/routes/routes.module';
import { ConfigModule } from '@nestjs/config';
import { ServeStaticModule } from '@nestjs/serve-static';
import { StateModule } from './modules/state/state.module';
import { SettingsModule } from './modules/settings/settings.module';

@Module({
  imports: [
    ConfigModule.forRoot(),
    MongooseModule.forRoot(process.env.DATABASE_URL),
    RoutesModule,
    StateModule,
    SettingsModule,
    ServeStaticModule.forRoot({
      rootPath: process.env.FILE_STORAGE,
    }),
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}

import { Module } from '@nestjs/common';
import { RoutesController } from './routes.controller';
import { RoutesService } from './routes.service';
import { Route, RouteSchema } from '../../schemas/route.schema';
import { MongooseModule } from '@nestjs/mongoose';
import { MulterModule } from '@nestjs/platform-express';

@Module({
  imports: [
    MongooseModule.forFeature([{ name: Route.name, schema: RouteSchema }]),
    MulterModule.register({
      dest: '../upload',
    }),
  ],
  controllers: [RoutesController],
  providers: [RoutesService],
})
export class RoutesModule {}

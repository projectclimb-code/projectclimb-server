import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { ConfigModule } from '@nestjs/config';
import { State, StateSchema } from 'src/schemas/state.schema';
import { StateService } from './state.service';
import { StateController } from './state.controller';
import { Route, RouteSchema } from 'src/schemas/route.schema';
import { Setting, SettingSchema } from 'src/schemas/setting.schema';

@Module({
  imports: [
    ConfigModule.forRoot(),
    MongooseModule.forFeature([{ name: State.name, schema: StateSchema }]),
    MongooseModule.forFeature([{ name: Route.name, schema: RouteSchema }]),
    MongooseModule.forFeature([{ name: Setting.name, schema: SettingSchema }]),
  ],
  controllers: [StateController],
  providers: [StateService],
})
export class StateModule {}

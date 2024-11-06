import { Model, Types } from 'mongoose';
import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { State } from '../../schemas/state.schema';
import { Route } from '../../schemas/route.schema';
import { Setting } from '../../schemas/setting.schema';

@Injectable()
export class StateService {
  constructor(
    @InjectModel(State.name) private stateModel: Model<State>,
    @InjectModel(Route.name) private routeModel: Model<Route>,
    @InjectModel(Setting.name) private settingsModel: Model<Setting>,
  ) {}

  async getState(): Promise<{ route: Route; settings: Setting }> {
    const state = await this.stateModel.findOne().exec();
    const route = await this.routeModel.findById(state.currentroute).exec();
    const settings = await this.settingsModel.findOne();
    return { route, settings };
  }

  async setState(currentroute: string): Promise<State> {
    const state = await this.stateModel.findOne().exec();
    state.currentroute = Types.ObjectId.createFromHexString(currentroute);
    return state.save();
  }
}

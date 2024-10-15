import { Model, Types } from 'mongoose';
import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { State } from '../../schemas/state.schema';
import { Route } from '../../schemas/route.schema';

@Injectable()
export class StateService {
  constructor(
    @InjectModel(State.name) private stateModel: Model<State>,
    @InjectModel(Route.name) private routeModel: Model<Route>,
  ) {}

  async getState(): Promise<Route> {
    const state = await this.stateModel.findOne().exec();
    return await this.routeModel.findById(state.currentroute).exec();
  }

  async setState(currentroute: string): Promise<State> {
    const state = await this.stateModel.findOne().exec();
    state.currentroute = Types.ObjectId.createFromHexString(currentroute);
    return state.save();
  }
}

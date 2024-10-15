import { Model } from 'mongoose';
import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Route } from '../../schemas/route.schema';
import { CreateRouteDto } from '../../dto/create-route.dto';

@Injectable()
export class RoutesService {
  constructor(@InjectModel(Route.name) private routeModel: Model<Route>) {}

  async create(createRouteDto: CreateRouteDto): Promise<Route> {
    const createdRoute = new this.routeModel(createRouteDto);
    return createdRoute.save();
  }

  async findAll(): Promise<Route[]> {
    return this.routeModel.find().exec();
  }
}

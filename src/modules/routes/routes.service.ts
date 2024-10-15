import { Model } from 'mongoose';
import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Route } from '../../schemas/route.schema';
import { CreateRouteDto } from '../../dto/create-route.dto';
import { UpdateRouteDto } from '../../dto/update-route.dto';
import * as fs from 'fs';

@Injectable()
export class RoutesService {
  constructor(@InjectModel(Route.name) private routeModel: Model<Route>) {}

  async create(createRouteDto: CreateRouteDto): Promise<Route> {
    const createdRoute = new this.routeModel(createRouteDto);
    createdRoute.createdAt = new Date();
    createdRoute.updatedAt = new Date();
    return createdRoute.save();
  }

  async findAll(): Promise<Route[]> {
    return await this.routeModel.find().exec();
  }

  async findOne(id: string): Promise<Route> {
    return await this.routeModel.findById(id).exec();
  }

  async updateOne(route: UpdateRouteDto): Promise<Route> {
    const routeInDb = await this.routeModel.findById(route.id).exec();
    for (const key in route) {
      if (route.hasOwnProperty(key) && key !== 'id') {
        routeInDb[key] = route[key];
      }
    }
    routeInDb.updatedAt = new Date();
    return routeInDb.save();
  }

  async deleteOne(id: string): Promise<any> {
    const route = await this.routeModel.findById(id).exec();
    if (route) {
      fs.unlink(route.path, (error) => {
        if (error) throw new Error('Could not delete file');
      });
      return route.deleteOne();
    } else {
      return 'Could not find route';
    }
  }
}

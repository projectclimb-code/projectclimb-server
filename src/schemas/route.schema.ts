import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type RouteDocument = HydratedDocument<Route>;

@Schema()
export class Route {
  @Prop()
  filename: string;

  @Prop()
  path: string;

  @Prop()
  size: number;

  @Prop()
  destination: string;

  @Prop()
  originalname: string;

  @Prop()
  mimetype: string;

  @Prop()
  name: string;

  @Prop()
  description: string;

  @Prop()
  difficulty: string;

  @Prop()
  offset_x: number;

  @Prop()
  offset_y: number;

  @Prop()
  zoom: number;
}

export const RouteSchema = SchemaFactory.createForClass(Route);

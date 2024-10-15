import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';
import { Types } from 'mongoose';

export type StateDocument = HydratedDocument<State>;

@Schema()
export class State {
  @Prop()
  currentroute: Types.ObjectId | null;
}

export const StateSchema = SchemaFactory.createForClass(State);

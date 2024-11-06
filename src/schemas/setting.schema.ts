import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type SettingDocument = HydratedDocument<Setting>;

@Schema({ _id: false })
export class DistortionCorrection {
  @Prop()
  keystonePoints: number[][];
}

@Schema()
export class Setting {
  @Prop()
  distortionCorrection: DistortionCorrection;
}

export const SettingSchema = SchemaFactory.createForClass(Setting);

import { Model } from 'mongoose';
import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Setting } from '../../schemas/setting.schema';
import { UpdateSettingDto } from '../../dto/update-setting.dto';

@Injectable()
export class SettingsService {
  constructor(
    @InjectModel(Setting.name) private settingModel: Model<Setting>,
  ) {}

  async findOne(): Promise<Setting> {
    let setting = await this.settingModel.findOne().exec();
    if (!setting) {
      setting = new this.settingModel({
        distortionCorrection: {
          keystonePoints: [
            [0, 0],
            [0, 0],
            [0, 0],
            [0, 0],
          ],
        },
      });
    }
    setting.save();
    delete setting._id;
    return setting;
  }

  async updateOne(newSetting: UpdateSettingDto): Promise<Setting> {
    const setting = await this.settingModel.findOne().exec();
    setting.distortionCorrection = newSetting.distortionCorrection;
    return setting.save();
  }
}

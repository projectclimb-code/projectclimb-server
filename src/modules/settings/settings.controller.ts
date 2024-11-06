import { Body, Controller, Get, Put, SerializeOptions } from '@nestjs/common';
import { SettingsService } from './settings.service';

@Controller('settings')
export class SettingsController {
  constructor(private readonly settingsService: SettingsService) {}

  @Put()
  update(@Body() body) {
    return this.settingsService.updateOne(body);
  }

  @SerializeOptions({
    excludePrefixes: ['_'],
  })
  @Get()
  findOne() {
    return this.settingsService.findOne();
  }
}

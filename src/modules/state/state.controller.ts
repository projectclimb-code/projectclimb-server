import { Body, Controller, Get, Put } from '@nestjs/common';
import { StateService } from './state.service';

@Controller('state')
export class StateController {
  constructor(private readonly stateService: StateService) {}

  @Get()
  async getState() {
    return await this.stateService.getState();
  }

  @Put()
  async setState(@Body() body) {
    const state = await this.stateService.setState(body.currentroute);
    return state;
  }
}
